from fastapi.testclient import TestClient

import app.detection.gemini_client as gemini_client_module
from app.api.main import app
from app.config import settings
from app.db.session import SessionLocal
from app.simulation.merchants import seed_merchants
from tests.fakes import FakeGeminiClient

client = TestClient(app)


def _patch_gemini(monkeypatch, response_text='{"action": "retry_now", "params": {}, "rationale": "test"}'):
    fake = FakeGeminiClient(response_text=response_text)
    monkeypatch.setattr(gemini_client_module, "_client", fake)
    return fake


def _seeded_merchant():
    db = SessionLocal()
    try:
        return seed_merchants(db)[0]
    finally:
        db.close()


def test_batch_run_ignores_api_key_when_auth_disabled(monkeypatch):
    _patch_gemini(monkeypatch)
    merchant = _seeded_merchant()

    resp = client.post("/batches/run", json={"merchant_id": str(merchant.id), "n_cases": 2, "seed": 1})
    assert resp.status_code == 200


def test_batch_run_requires_api_key_when_auth_enabled(monkeypatch):
    _patch_gemini(monkeypatch)
    monkeypatch.setattr(settings, "require_merchant_api_key", True)
    merchant = _seeded_merchant()

    missing = client.post("/batches/run", json={"merchant_id": str(merchant.id), "n_cases": 2, "seed": 1})
    assert missing.status_code == 401

    wrong = client.post(
        "/batches/run",
        json={"merchant_id": str(merchant.id), "n_cases": 2, "seed": 1},
        headers={"X-API-Key": "wrong-key"},
    )
    assert wrong.status_code == 401

    correct = client.post(
        "/batches/run",
        json={"merchant_id": str(merchant.id), "n_cases": 2, "seed": 1},
        headers={"X-API-Key": merchant.api_key},
    )
    assert correct.status_code == 200


def test_run_due_jobs_requires_api_key_when_scoped_and_auth_enabled(monkeypatch):
    monkeypatch.setattr(settings, "require_merchant_api_key", True)
    merchant = _seeded_merchant()

    scoped_missing_key = client.post("/jobs/run-due", params={"merchant_id": str(merchant.id)})
    assert scoped_missing_key.status_code == 401

    scoped_with_key = client.post(
        "/jobs/run-due", params={"merchant_id": str(merchant.id)}, headers={"X-API-Key": merchant.api_key}
    )
    assert scoped_with_key.status_code == 200

    # Unscoped (no merchant_id) has no single merchant's key to check against.
    unscoped = client.post("/jobs/run-due")
    assert unscoped.status_code == 200
