"""Test-wide environment, applied before any app module imports settings.

Disables LLM rate-limit pacing and backoff sleeps so tests exercising the
resilience layer's fallback paths stay fast and deterministic (os.environ
takes precedence over .env in pydantic-settings).
"""
import os

os.environ.setdefault("LLM_REQUESTS_PER_MINUTE", "0")
os.environ.setdefault("LLM_BACKOFF_BASE_SECONDS", "0")
