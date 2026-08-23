"""Orchestrates detection: rules first, Gemini fallback, writes the
`detected` and `diagnosed` AuditEvents (PRD §11 — every step persisted at
the time it happens, nothing inferred after the fact).

Receivables are out of scope here — their root-cause taxonomy (overdue
buckets, disputed) is deterministic from `due_at`/a dispute flag and is
built in Phase 6.
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.llm_classifier import classify_by_llm
from app.detection.rules import classify_by_rules
from app.models import AuditEvent, Case

PAYMENT_LIKE_TYPES = {"payment_failure", "mandate_failure"}


def detect_and_diagnose_case(db: Session, case: Case, llm_client: Any = None) -> Case:
    if case.type not in PAYMENT_LIKE_TYPES:
        return case

    db.add(
        AuditEvent(
            case_id=case.id,
            event_type="detected",
            actor="system",
            payload={"case_type": case.type, "amount": float(case.amount)},
        )
    )

    rule_root_cause = classify_by_rules(case.raw_failure_reason or "")
    if rule_root_cause is not None:
        root_cause, confidence, source, actor = rule_root_cause, 1.0, "rule", "system"
    else:
        llm_result = classify_by_llm(case.raw_failure_reason or "", client=llm_client)
        root_cause, confidence, source, actor = llm_result["root_cause"], llm_result["confidence"], "llm", "llm"

    case.root_cause = root_cause
    db.add(
        AuditEvent(
            case_id=case.id,
            event_type="diagnosed",
            actor=actor,
            payload={"root_cause": root_cause, "confidence": confidence, "source": source},
        )
    )
    return case


def run_detection_on_batch(db: Session, llm_client: Any = None) -> list[Case]:
    cases = (
        db.execute(
            select(Case).where(Case.root_cause.is_(None), Case.type.in_(PAYMENT_LIKE_TYPES))
        )
        .scalars()
        .all()
    )
    for case in cases:
        detect_and_diagnose_case(db, case, llm_client=llm_client)
    db.commit()
    return list(cases)
