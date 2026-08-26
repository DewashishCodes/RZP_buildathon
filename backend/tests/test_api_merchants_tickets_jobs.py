from fastapi.testclient import TestClient

import app.detection.gemini_client as gemini_client_module
from app.api.main import app
from app.db.session import SessionLocal
from app.simulation.merchants import DEMO_MERCHANTS, seed_merchants
from tests.fakes import FakeGeminiClient

client = TestClient(app)


def _patch_gemini(monkeypatch, response_text='{"action": "retry_now", "params": {}, "rationale": "test"}'):
    fake = FakeGeminiClient(response_text=response_text)
    monkeypatch.setattr(gemini_client_module, "_client", fake)
    return fake


def _demo_merchant_id() -> str:
    # This test file never exercises the app's real startup lifespan (a
    # plain TestClient() without `with` never fires it), so merchants must
    # be seeded explicitly per test rather than assumed to exist - relying
    # on another test file having leaked committed rows into the shared
    # dev DB is exactly the cross-test coupling db_transaction isolation
    # (tests/conftest.py) exists to catch.
    db = SessionLocal()
    try:
        return str(seed_merchants(db)[0].id)
    finally:
        db.close()


def test_list_merchants_returns_demo_merchants():
    _demo_merchant_id()
    resp = client.get("/merchants")
    assert resp.status_code == 200
    data = resp.json()
    slugs = {m["slug"] for m in data}
    assert slugs == {m["slug"] for m in DEMO_MERCHANTS}


def test_escalated_case_produces_a_listed_ticket(monkeypatch):
    _patch_gemini(monkeypatch)
    merchant_id = _demo_merchant_id()

    # a batch with a fraud-heavy seed reliably produces at least one
    # escalation without needing many cases
    run_resp = client.post("/batches/run", json={"merchant_id": merchant_id, "n_cases": 20, "seed": 42})
    batch_id = run_resp.json()["batch_id"]
    cases = client.get("/cases", params={"batch_id": batch_id, "status": "escalated_human"}).json()
    assert len(cases) >= 1

    tickets = client.get("/tickets", params={"merchant_id": merchant_id}).json()
    escalated_case_ids = {c["id"] for c in cases}
    ticket_case_ids = {t["case_id"] for t in tickets}
    assert escalated_case_ids.issubset(ticket_case_ids)


def test_get_ticket_404_for_unknown_ticket():
    import uuid

    resp = client.get(f"/tickets/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_run_due_jobs_advances_scheduled_cases(monkeypatch):
    _patch_gemini(monkeypatch)
    merchant_id = _demo_merchant_id()

    run_resp = client.post("/batches/run", json={"merchant_id": merchant_id, "n_cases": 15, "seed": 9, "instant": False})
    batch_id = run_resp.json()["batch_id"]
    scheduled_before = client.get("/cases/scheduled", params={"merchant_id": merchant_id}).json()
    assert any(c["batch_id"] == batch_id for c in scheduled_before)

    resp = client.post("/jobs/run-due", params={"merchant_id": merchant_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] >= 1
