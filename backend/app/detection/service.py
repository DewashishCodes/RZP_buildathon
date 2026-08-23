"""Orchestrates detection: rules/deterministic-bucket first, Gemini
fallback only for payment/mandate cases whose failure message is
ambiguous. Writes the `detected` and `diagnosed` AuditEvents (PRD §11 —
every step persisted at the time it happens, nothing inferred after the
fact).
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.detection.llm_classifier import classify_by_llm
from app.detection.receivables import classify_receivable
from app.detection.rules import classify_by_rules
from app.models import AuditEvent, Case

PAYMENT_LIKE_TYPES = {"payment_failure", "mandate_failure"}
RECEIVABLE_TYPES = {"receivable"}
DETECTABLE_TYPES = PAYMENT_LIKE_TYPES | RECEIVABLE_TYPES


def detect_and_diagnose_case(db: Session, case: Case, llm_client: Any = None, now: datetime | None = None) -> Case:
    if case.type not in DETECTABLE_TYPES:
        return case

    db.add(
        AuditEvent(
            case_id=case.id,
            event_type="detected",
            actor="system",
            payload={"case_type": case.type, "amount": float(case.amount)},
        )
    )

    if case.type in PAYMENT_LIKE_TYPES:
        rule_root_cause = classify_by_rules(case.raw_failure_reason or "")
        if rule_root_cause is not None:
            root_cause, confidence, source, actor = rule_root_cause, 1.0, "rule", "system"
        else:
            llm_result = classify_by_llm(case.raw_failure_reason or "", client=llm_client)
            root_cause, confidence, source, actor = llm_result["root_cause"], llm_result["confidence"], "llm", "llm"
    else:
        now = now or datetime.now(timezone.utc)
        root_cause, confidence, source, actor = classify_receivable(case, now=now), 1.0, "rule", "system"

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


def run_detection_on_batch(
    db: Session, llm_client: Any = None, now: datetime | None = None, case_ids: list | None = None
) -> list[Case]:
    stmt = select(Case).where(Case.root_cause.is_(None), Case.type.in_(DETECTABLE_TYPES))
    if case_ids is not None:
        stmt = stmt.where(Case.id.in_(case_ids))
    cases = db.execute(stmt).scalars().all()
    for case in cases:
        detect_and_diagnose_case(db, case, llm_client=llm_client, now=now)
    db.commit()
    return list(cases)
