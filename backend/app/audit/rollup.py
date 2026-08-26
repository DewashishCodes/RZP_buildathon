"""Batch rollup queries (PRD §11 dashboard requirements): total Rs. at
risk/recovered, recovery rate overall and by root cause, plus proof
counters - how many times a stopping rule fired, how many times
compliance actually substituted an action - so the dashboard can show
guardrails aren't decorative, not just that they exist.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, BatchRun, Case

STOPPING_RULE_EVENT_TYPES = ("stopped", "escalated")


def list_batches(db: Session, merchant_id: uuid.UUID | None = None, limit: int = 15) -> list[dict]:
    """Batch history for the dashboard's "recent runs" picker - derived from
    the cases table (so sync-era batches appear too), enriched with the
    BatchRun lifecycle row where one exists."""
    stmt = (
        select(
            Case.batch_id,
            func.count().label("total_cases"),
            func.coalesce(func.sum(Case.amount), 0).label("total_at_risk"),
            func.coalesce(func.sum(Case.recovered_amount), 0).label("total_recovered"),
            func.max(Case.created_at).label("last_activity"),
        )
        .where(Case.batch_id.is_not(None))
        .group_by(Case.batch_id)
        .order_by(func.max(Case.created_at).desc())
        .limit(limit)
    )
    if merchant_id is not None:
        stmt = stmt.where(Case.merchant_id == merchant_id)

    rows = db.execute(stmt).all()
    if not rows:
        return []

    runs = {
        run.id: run
        for run in db.execute(
            select(BatchRun).where(BatchRun.id.in_([row.batch_id for row in rows]))
        ).scalars().all()
    }

    items = []
    for batch_id, total_cases, at_risk, recovered, last_activity in rows:
        run = runs.get(batch_id)
        items.append(
            {
                "batch_id": str(batch_id),
                # queued/running/complete/failed when tracked; sync-era
                # batches finished inside their request, so 'complete'.
                "phase": run.phase if run is not None else "complete",
                "created_at": last_activity.isoformat() if last_activity else None,
                "total_cases": int(total_cases),
                "total_at_risk": float(at_risk or 0),
                "total_recovered": float(recovered or 0),
                "recovery_rate": float(recovered or 0) / float(at_risk) if at_risk else 0.0,
            }
        )
    return items


def batch_summary(db: Session, batch_id: uuid.UUID) -> dict | None:
    case_filter = Case.batch_id == batch_id

    total_cases = db.scalar(select(func.count()).select_from(Case).where(case_filter)) or 0
    if total_cases == 0:
        return None

    total_at_risk = db.scalar(select(func.sum(Case.amount)).where(case_filter)) or 0
    total_recovered = db.scalar(select(func.sum(Case.recovered_amount)).where(case_filter)) or 0
    recovery_rate = float(total_recovered) / float(total_at_risk) if total_at_risk else 0.0

    by_root_cause: dict[str, dict] = {}
    rows = db.execute(
        select(Case.root_cause, func.sum(Case.amount), func.sum(Case.recovered_amount))
        .where(case_filter)
        .group_by(Case.root_cause)
    ).all()
    for root_cause, at_risk, recovered in rows:
        at_risk = float(at_risk or 0)
        recovered = float(recovered or 0)
        by_root_cause[root_cause or "undiagnosed"] = {
            "at_risk": at_risk,
            "recovered": recovered,
            "recovery_rate": recovered / at_risk if at_risk else 0.0,
        }

    status_counts = dict(
        db.execute(select(Case.status, func.count()).where(case_filter).group_by(Case.status)).all()
    )

    stopping_rule_triggers = (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .join(Case, Case.id == AuditEvent.case_id)
            .where(case_filter, AuditEvent.event_type.in_(STOPPING_RULE_EVENT_TYPES))
        )
        or 0
    )

    compliance_substitutions = (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .join(Case, Case.id == AuditEvent.case_id)
            .where(
                case_filter,
                AuditEvent.event_type == "compliance_check",
                AuditEvent.payload["substituted"].as_boolean().is_(True),
            )
        )
        or 0
    )

    return {
        "batch_id": str(batch_id),
        "total_cases": total_cases,
        "total_at_risk": float(total_at_risk),
        "total_recovered": float(total_recovered),
        "recovery_rate": recovery_rate,
        "by_root_cause": by_root_cause,
        "status_counts": status_counts,
        "stopping_rule_triggers": stopping_rule_triggers,
        "compliance_substitutions": compliance_substitutions,
    }


def guardrail_interventions(db: Session, batch_id: uuid.UUID, limit: int = 20) -> list[dict]:
    """The stories behind the two proof counters, as a drillable feed:
    every stopping-rule fire (stopped/escalated events) and every
    compliance substitution in the batch, newest first. Turns "guardrails
    fired N times" into something judges can actually click into."""
    rows = db.execute(
        select(AuditEvent, Case.id)
        .join(Case, Case.id == AuditEvent.case_id)
        .where(
            Case.batch_id == batch_id,
            (
                AuditEvent.event_type.in_(STOPPING_RULE_EVENT_TYPES)
                | (
                    (AuditEvent.event_type == "compliance_check")
                    & AuditEvent.payload["substituted"].as_boolean().is_(True)
                )
            ),
        )
        .order_by(AuditEvent.timestamp.desc())
        .limit(limit)
    ).all()

    feed = []
    for event, case_id in rows:
        payload = event.payload or {}
        is_stopping_rule = event.event_type in STOPPING_RULE_EVENT_TYPES
        feed.append(
            {
                "case_id": str(case_id),
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "kind": "stopping_rule" if is_stopping_rule else "compliance_substitution",
                "rule": payload.get("rule"),
                "reason": payload.get("reason") or payload.get("action"),
                "event_type": event.event_type,
            }
        )
    return feed


def recovery_curve(db: Session, batch_id: uuid.UUID) -> list[dict]:
    """Cumulative Rs. recovered over the batch's processing timeline.
    Each recovered case contributes its full recovered_amount once - at its
    final outcome_recorded event - and points are ordered by that moment,
    so the series only ever goes up as the agent works."""
    amounts = {
        case.id: float(case.recovered_amount or 0)
        for case in db.execute(select(Case).where(Case.batch_id == batch_id, Case.status == "recovered")).scalars().all()
    }
    if not amounts:
        return []

    moments = (
        db.execute(
            select(AuditEvent.case_id, func.max(AuditEvent.timestamp))
            .join(Case, Case.id == AuditEvent.case_id)
            .where(
                AuditEvent.case_id.in_(list(amounts)),
                AuditEvent.event_type == "outcome_recorded",
            )
            .group_by(AuditEvent.case_id)
        )
        .all()
    )

    points: list[dict] = []
    cumulative = 0.0
    for _case_id, timestamp in sorted(moments, key=lambda row: row[1]):
        cumulative += amounts[_case_id]
        points.append(
            {
                "timestamp": timestamp.isoformat() if timestamp else None,
                "cumulative_recovered": round(cumulative, 2),
            }
        )
    return points
