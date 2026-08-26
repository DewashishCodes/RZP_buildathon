"""Lazy singleton Gemini client, built only when first needed so importing
this module (or anything that imports it) never requires GEMINI_API_KEY to
be set — e.g. for tests that always inject a fake client.
"""
from google import genai

from app.config import settings

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            # Fail fast with an actionable message instead of an opaque
            # auth error on the first real call. Tests never hit this -
            # they inject fake clients or monkeypatch _client directly.
            raise RuntimeError(
                "GEMINI_API_KEY is not set - add it to backend/.env (see .env.example)."
            )
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client
