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
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client
