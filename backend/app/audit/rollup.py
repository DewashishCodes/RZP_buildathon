"""Batch rollup queries (PRD §11 dashboard requirements): total Rs. at
risk/recovered, recovery rate overall and by root cause, plus proof
counters - how many times a stopping rule fired, how many times
compliance actually substituted an action - so the dashboard can show
guardrails aren't decorative, not just that they exist.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Case

STOPPING_RULE_EVENT_TYPES = ("stopped", "escalated")


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
