"""Batch runner (PRD §9.1, §12): detection -> policy -> execution across a
seeded batch, looping each case through rounds until it reaches a terminal
status, respecting the guardrails in app/policy/guardrails.py.

Covers all three leak types - payment_failure, mandate_failure, and (as
of Phase 6) receivable - through the same code path. Receivables get
their root_cause from the deterministic due_at/disputed bucketing in
app/detection/receivables.py rather than the LLM classifier, but from
here on everything (allowed action subset, guardrails, connectors) is
already generic across case types.

Time is simulated, not real: each case gets its own `sim_now` clock that
jumps forward ~25h (or to a retry_scheduled's retry_date, if later) after
every round, so a whole multi-week recovery journey - and the guardrails
that depend on elapsed time (retry spacing, case age) - plays out within a
single script run instead of actually waiting.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.detection.service import run_detection_on_batch
from app.execution.connectors import execute_contact_action, execute_voice_call
from app.models import Attempt, AuditEvent, Case
from app.policy.channels import determine_channel
from app.policy.engine import decide_action

TERMINAL_STATUSES = {"recovered", "written_off", "escalated_human"}
RUNNER_SCOPE_TYPES = {"payment_failure", "mandate_failure", "receivable"}
MAX_ROUNDS_PER_CASE = 6
ROUND_ADVANCE = timedelta(hours=25)


def run_batch(db: Session, llm_client=None, now: datetime | None = None, case_ids: list | None = None) -> dict:
    """Runs the full pipeline. If case_ids is given, scopes detection and
    execution to exactly those cases (used by scenario-specific demo
    scripts so they don't sweep every accumulated case in the dev DB);
    otherwise processes every open case of the in-scope types.
    """
    now = now or datetime.now(timezone.utc)

    run_detection_on_batch(db, llm_client=llm_client, now=now, case_ids=case_ids)

    stmt = select(Case).where(Case.type.in_(RUNNER_SCOPE_TYPES), Case.status.notin_(TERMINAL_STATUSES))
    if case_ids is not None:
        stmt = stmt.where(Case.id.in_(case_ids))
    cases = db.execute(stmt).scalars().all()
    for case in cases:
        _run_case_to_terminal(db, case, llm_client=llm_client, start_now=now)

    db.commit()
    return summarize(db)


def _run_case_to_terminal(db: Session, case: Case, llm_client, start_now: datetime) -> None:
    sim_now = start_now

    for _ in range(MAX_ROUNDS_PER_CASE):
        db.refresh(case)
        if case.status in TERMINAL_STATUSES:
            return

        customer = case.customer
        attempts = list(case.attempts)

        decision = decide_action(db, case, customer, attempts, now=sim_now, llm_client=llm_client)
        action, params = decision["action"], decision["params"]

        if action == "no_action":
            return

        if action == "stop_case":
            case.status = "written_off"
            case.outcome = "unrecovered"
            db.add(case)
            if decision["source"] != "stopping_rule":
                db.add(
                    AuditEvent(
                        id=uuid.uuid4(),
                        case_id=case.id,
                        event_type="stopped",
                        actor="llm",
                        payload={"action": action, "rule": decision.get("rule"), "reason": decision.get("reason")},
                    )
                )
            db.commit()
            return

        if action == "escalate_human":
            case.status = "escalated_human"
            db.add(case)
            if decision["source"] != "stopping_rule":
                db.add(
                    AuditEvent(
                        id=uuid.uuid4(),
                        case_id=case.id,
                        event_type="escalated",
                        actor="llm",
                        payload={"action": action, "rule": decision.get("rule"), "reason": decision.get("reason")},
                    )
                )
            db.commit()
            return

        channel = determine_channel(action, customer.preferred_channel)
        if action == "voice_call":
            outcome = execute_voice_call(case, customer, now=sim_now, llm_client=llm_client)
        else:
            outcome = execute_contact_action(case, customer, action, now=sim_now)

        attempt = Attempt(
            id=uuid.uuid4(),
            case_id=case.id,
            timestamp=sim_now,
            channel=channel,
            action=action,
            compliance_check={"passed": not decision["substituted"], "rule": decision.get("rule"), "reason": decision.get("reason")},
            outcome=outcome["attempt_outcome"],
            promise_to_pay_date=outcome["promise_to_pay_date"],
            transcript=outcome.get("transcript"),
        )
        db.add(attempt)
        db.add(
            AuditEvent(
                id=uuid.uuid4(),
                case_id=case.id,
                attempt_id=attempt.id,
                event_type="action_executed",
                actor="system",
                payload={"action": action, "channel": channel},
            )
        )
        db.add(
            AuditEvent(
                id=uuid.uuid4(),
                case_id=case.id,
                attempt_id=attempt.id,
                event_type="outcome_recorded",
                actor="system",
                payload={
                    "outcome": outcome["attempt_outcome"],
                    "recovered": outcome["recovered"],
                    "recovered_amount": outcome["recovered_amount"],
                },
            )
        )

        if outcome["recovered"]:
            case.status = "recovered"
            case.outcome = "recovered"
            case.recovered_amount = outcome["recovered_amount"]
            db.add(case)
            db.commit()
            return

        case.status = "recovering"
        db.add(case)
        db.commit()

        sim_now = sim_now + ROUND_ADVANCE
        retry_date = params.get("retry_date")
        if action == "retry_scheduled" and retry_date is not None:
            if retry_date.tzinfo is None:
                retry_date = retry_date.replace(tzinfo=timezone.utc)
            sim_now = max(sim_now, retry_date + timedelta(hours=1))

    # Safety cap: guardrails should always terminate a case well before
    # this many rounds. If they somehow didn't, force resolution rather
    # than leaving the case in limbo (PRD §9.2's no-limbo requirement).
    case.status = "escalated_human"
    db.add(case)
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            case_id=case.id,
            event_type="escalated",
            actor="system",
            payload={"rule": "max_rounds_safety_cap", "reason": f"case did not reach a terminal state within {MAX_ROUNDS_PER_CASE} rounds"},
        )
    )
    db.commit()


def summarize(db: Session) -> dict:
    total_at_risk = db.scalar(select(func.sum(Case.amount)).where(Case.type.in_(RUNNER_SCOPE_TYPES))) or 0
    total_recovered = (
        db.scalar(select(func.sum(Case.recovered_amount)).where(Case.type.in_(RUNNER_SCOPE_TYPES))) or 0
    )
    total_cases = db.scalar(select(func.count()).select_from(Case).where(Case.type.in_(RUNNER_SCOPE_TYPES))) or 0

    status_counts = dict(
        db.execute(
            select(Case.status, func.count()).where(Case.type.in_(RUNNER_SCOPE_TYPES)).group_by(Case.status)
        ).all()
    )

    recovery_rate = float(total_recovered) / float(total_at_risk) if total_at_risk else 0.0

    return {
        "total_cases": total_cases,
        "total_at_risk": float(total_at_risk),
        "total_recovered": float(total_recovered),
        "recovery_rate": recovery_rate,
        "status_counts": status_counts,
    }
