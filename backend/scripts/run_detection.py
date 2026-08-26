"""CLI: run the detection layer over every seeded payment/mandate case that
doesn't have a root_cause yet, and print case -> root_cause -> confidence
-> source so it can be eyeballed (Phase 2 manual walkthrough).

Usage:
    python scripts/run_detection.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.detection.service import run_detection_on_batch
from app.models import AuditEvent


def main() -> None:
    db = SessionLocal()
    try:
        cases = run_detection_on_batch(db)
        if not cases:
            print("No undiagnosed payment/mandate cases found — seed a batch first.")
            return

        # One grouped query for every diagnosed event instead of a per-case
        # lookup in the loop below (N+1 on the old version).
        diag_events = {
            event.case_id: event
            for event in db.execute(
                select(AuditEvent)
                .where(AuditEvent.case_id.in_([c.id for c in cases]), AuditEvent.event_type == "diagnosed")
                .order_by(AuditEvent.timestamp.asc())
            )
            .scalars()
            .all()
        }

        print(f"Diagnosed {len(cases)} cases:\n")
        print(f"{'case_id':38s} {'type':16s} {'root_cause':20s} {'confidence':10s} source")
        sources: list[str] = []
        for case in cases:
            # Later writes win: dict keeps the last (most recent) event per case.
            diag_event = diag_events.get(case.id)
            confidence = diag_event.payload.get("confidence") if diag_event else None
            source = diag_event.payload.get("source") if diag_event else None
            sources.append(source)
            print(f"{str(case.id):38s} {case.type:16s} {str(case.root_cause):20s} {str(confidence):10s} {source}")

        rule_count = sources.count("rule")
        llm_count = sources.count("llm")
        print(f"\nSource breakdown: rule={rule_count} llm={llm_count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
