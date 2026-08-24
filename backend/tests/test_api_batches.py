"""API-level tests for /batches routes. Monkeypatches the module-level
Gemini client singleton (app.detection.gemini_client._client) rather than
passing a client explicitly - the HTTP routes don't accept a client
override (production always uses the real one), so this is the one place
tests reach past the module boundary to keep real Gemini calls out of
the test suite.
"""
from fastapi.testclient import TestClient

import app.detection.gemini_client as gemini_client_module
from app.api.main import app
from app.db.session import SessionLocal
from app.simulation.guaranteed_cases import build_guaranteed_cases
from app.simulation.merchants import seed_merchants
from tests.fakes import FakeGeminiClient

client = TestClient(app)

N_GUARANTEED = len(build_guaranteed_cases()[1])


def _patch_gemini(monkeypatch, response_text='{"action": "retry_now", "params": {}, "rationale": "test"}'):
    fake = FakeGeminiClient(response_text=response_text)
    monkeypatch.setattr(gemini_client_module, "_client", fake)
    return fake


def _demo_merchant_id() -> str:
    db = SessionLocal()
    try:
        return str(seed_merchants(db)[0].id)
    finally:
        db.close()


def test_run_batch_returns_batch_id_and_summary(monkeypatch):
    _patch_gemini(monkeypatch)
    merchant_id = _demo_merchant_id()

    resp = client.post("/batches/run", json={"merchant_id": merchant_id, "n_cases": 5, "seed": 1})

    assert resp.status_code == 200
    data = resp.json()
    assert "batch_id" in data
    assert data["n_cases"] == 5 + N_GUARANTEED
    assert data["n_customers"] == 5 + N_GUARANTEED
    assert "summary" in data


def test_get_batch_summary_after_run(monkeypatch):
    _patch_gemini(monkeypatch)
    merchant_id = _demo_merchant_id()

    run_resp = client.post("/batches/run", json={"merchant_id": merchant_id, "n_cases": 5, "seed": 2})
    batch_id = run_resp.json()["batch_id"]

    summary_resp = client.get(f"/batches/{batch_id}/summary")

    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["batch_id"] == batch_id
    assert summary["total_cases"] >= 1
    assert "by_root_cause" in summary
    assert "stopping_rule_triggers" in summary
    assert "compliance_substitutions" in summary


def test_get_batch_summary_404_for_unknown_batch():
    import uuid

    resp = client.get(f"/batches/{uuid.uuid4()}/summary")
    assert resp.status_code == 404


def test_run_batch_non_instant_leaves_cases_scheduled(monkeypatch):
    _patch_gemini(monkeypatch)
    merchant_id = _demo_merchant_id()

    resp = client.post("/batches/run", json={"merchant_id": merchant_id, "n_cases": 20, "seed": 5, "instant": False})

    assert resp.status_code == 200
    batch_id = resp.json()["batch_id"]
    cases = client.get("/cases", params={"batch_id": batch_id}).json()
    # every case got exactly one round - none should have made it past a
    # single retry_now attempt to a terminal state this fast, so at least
    # some must still be "recovering" with a scheduled next_action_at.
    assert any(c["status"] == "recovering" and c["next_action_at"] is not None for c in cases)
