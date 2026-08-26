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


def test_background_batch_completes_and_progress_tracks_it(monkeypatch):
    """background=true returns immediately; the TestClient runs the
    BackgroundTask before the POST call returns, so progress is already
    'complete' here - this pins the wiring (row created, phase flipped,
    counts derived from cases) rather than real-world timing."""
    _patch_gemini(monkeypatch)
    merchant_id = _demo_merchant_id()
    n_cases = 4

    resp = client.post(
        "/batches/run",
        json={"merchant_id": merchant_id, "n_cases": n_cases, "seed": 9, "background": True},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["n_cases"] == n_cases + N_GUARANTEED
    assert data["summary"] == {}  # empty in background mode - poll for it

    progress = client.get(f"/batches/{data['batch_id']}/progress")
    assert progress.status_code == 200
    p = progress.json()
    assert p["phase"] == "complete"
    assert p["total_cases"] == n_cases + N_GUARANTEED
    assert p["resolved_cases"] == p["total_cases"]
    assert p["at_risk_amount"] > 0

    # The completed rollup is stored on the batch row and matches the
    # summary endpoint.
    summary = client.get(f"/batches/{data['batch_id']}/summary").json()
    db = SessionLocal()
    try:
        from app.models import BatchRun

        run = db.get(BatchRun, __import__("uuid").UUID(data["batch_id"]))
        assert run is not None and run.phase == "complete"
        assert run.summary is not None
        assert run.summary["total_cases"] == summary["total_cases"]
    finally:
        db.close()


def test_background_batch_failure_recorded_not_raised(monkeypatch):
    from app.api import batches as batches_module

    _patch_gemini(monkeypatch)
    merchant_id = _demo_merchant_id()

    def explode(*args, **kwargs):
        raise RuntimeError("pipeline blew up")

    monkeypatch.setattr(batches_module, "run_batch", explode)

    resp = client.post(
        "/batches/run", json={"merchant_id": merchant_id, "n_cases": 2, "seed": 10, "background": True}
    )
    assert resp.status_code == 200
    batch_id = resp.json()["batch_id"]

    progress = client.get(f"/batches/{batch_id}/progress").json()
    assert progress["phase"] == "failed"
    assert "pipeline blew up" in progress["error"]

    db = SessionLocal()
    try:
        db.expire_all()  # _execute_background_batch wrote via its own session
        from app.models import BatchRun

        run = db.get(BatchRun, __import__("uuid").UUID(batch_id))
        assert run is not None and run.phase == "failed"
        assert "pipeline blew up" in run.error
    finally:
        db.close()


def test_batch_progress_404_for_unknown_or_empty_batch():
    import uuid

    resp = client.get(f"/batches/{uuid.uuid4()}/progress")
    assert resp.status_code == 404
