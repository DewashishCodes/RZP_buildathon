"""Orchestrates the policy flow (PRD §9.1): LLM proposes -> code-level
guardrails approve/reject/rewrite -> every step logged as an AuditEvent.
Stopping rules are checked before the LLM is even called - there is no
point asking the LLM to reason about a case that must be auto-escalated.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.policy.action_space import get_allowed_actions
from app.policy.guardrails import check_compliance, check_stopping_rules
from app.policy.proposer import propose_action


def decide_action(
    db: Session,
    case,
    customer,
    attempts: list,
    now: datetime | None = None,
    llm_client: Any = None,
) -> dict:
    """Runs the full propose -> guardrail pipeline for one case, writing
    AuditEvents along the way, and returns the final decision:
    {action, params, source: "stopping_rule"|"llm", rule, substituted}
    """
    now = now or datetime.now(timezone.utc)

    stopping_result = check_stopping_rules(case, customer, attempts, now=now)
    if stopping_result is not None:
        db.add(
            AuditEvent(
                case_id=case.id,
                event_type="stopped" if stopping_result["action"] == "stop_case" else "escalated",
                actor="system",
                payload={
                    "action": stopping_result["action"],
                    "params": _jsonable(stopping_result["params"]),
                    "rule": stopping_result["rule"],
                    "reason": stopping_result["reason"],
                },
            )
        )
        return {
            "action": stopping_result["action"],
            "params": stopping_result["params"],
            "source": "stopping_rule",
            "rule": stopping_result["rule"],
            "reason": stopping_result["reason"],
            "substituted": False,
        }

    allowed_actions = get_allowed_actions(case.type)
    proposal = propose_action(case, customer, attempts, allowed_actions, client=llm_client, now=now)
    db.add(
        AuditEvent(
            case_id=case.id,
            event_type="action_proposed",
            actor="llm",
            payload={
                "action": proposal["action"],
                "params": _jsonable(proposal["params"]),
                "rationale": proposal["rationale"],
            },
        )
    )

    verdict = check_compliance(proposal["action"], proposal["params"], case, customer, attempts, now=now)
    db.add(
        AuditEvent(
            case_id=case.id,
            event_type="compliance_check",
            actor="system",
            payload={
                "passed": verdict["passed"],
                "proposed_action": proposal["action"],
                "final_action": verdict["action"],
                "rule": verdict["rule"],
                "reason": verdict["reason"],
                "substituted": verdict["substituted"],
            },
        )
    )

    return {
        "action": verdict["action"],
        "params": verdict["params"],
        "source": "llm",
        "rule": verdict["rule"],
        "reason": verdict["reason"],
        "substituted": verdict["substituted"],
    }


def _jsonable(params: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in params.items()}
