import uuid

from fastapi.testclient import TestClient

import app.detection.gemini_client as gemini_client_module
from app.api.main import app
from tests.fakes import FakeGeminiClient

client = TestClient(app)


def _patch_gemini(monkeypatch, response_text='{"action": "retry_now", "params": {}, "rationale": "test"}'):
    fake = FakeGeminiClient(response_text=response_text)
    monkeypatch.setattr(gemini_client_module, "_client", fake)
    return fake


def test_list_cases_filters_by_batch_id(monkeypatch):
    _patch_gemini(monkeypatch)

    run_resp = client.post("/batches/run", json={"n_cases": 4, "seed": 3})
    batch_id = run_resp.json()["batch_id"]

    resp = client.get("/cases", params={"batch_id": batch_id})

    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) == 4
    assert all(c["batch_id"] == batch_id for c in cases)


def test_get_case_returns_full_timeline(monkeypatch):
    _patch_gemini(monkeypatch)

    run_resp = client.post("/batches/run", json={"n_cases": 3, "seed": 4})
    batch_id = run_resp.json()["batch_id"]
    cases = client.get("/cases", params={"batch_id": batch_id}).json()
    case_id = cases[0]["id"]

    resp = client.get(f"/cases/{case_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["case"]["id"] == case_id
    assert isinstance(data["events"], list)
    assert len(data["events"]) >= 1
    assert isinstance(data["attempts"], list)

    timestamps = [e["timestamp"] for e in data["events"]]
    assert timestamps == sorted(timestamps)


def test_get_case_404_for_unknown_case():
    resp = client.get(f"/cases/{uuid.uuid4()}")
    assert resp.status_code == 404
