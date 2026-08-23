from app.detection.llm_classifier import FALLBACK_ROOT_CAUSE, classify_by_llm
from tests.fakes import FakeGeminiClient


def test_classify_by_llm_parses_valid_json():
    client = FakeGeminiClient(response_text='{"root_cause": "issuer_declined", "confidence": 0.82}')
    result = classify_by_llm("Transaction could not be completed.", client=client)
    assert result == {"root_cause": "issuer_declined", "confidence": 0.82}
    assert len(client.calls) == 1


def test_classify_by_llm_strips_markdown_fences():
    client = FakeGeminiClient(response_text='```json\n{"root_cause": "bank_timeout", "confidence": 0.6}\n```')
    result = classify_by_llm("Generic decline.", client=client)
    assert result == {"root_cause": "bank_timeout", "confidence": 0.6}


def test_classify_by_llm_falls_back_on_malformed_json():
    client = FakeGeminiClient(response_text="not json at all")
    result = classify_by_llm("Generic decline.", client=client)
    assert result["root_cause"] == FALLBACK_ROOT_CAUSE
    assert result["confidence"] == 0.0


def test_classify_by_llm_falls_back_on_invalid_root_cause():
    client = FakeGeminiClient(response_text='{"root_cause": "not_a_real_cause", "confidence": 0.9}')
    result = classify_by_llm("Generic decline.", client=client)
    assert result["root_cause"] == FALLBACK_ROOT_CAUSE
    assert result["confidence"] == 0.0


def test_classify_by_llm_falls_back_on_missing_confidence():
    client = FakeGeminiClient(response_text='{"root_cause": "card_expired"}')
    result = classify_by_llm("Generic decline.", client=client)
    assert result["root_cause"] == "card_expired"
    assert result["confidence"] == 0.0
