from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://recovery:recovery@localhost:5432/revenue_recovery"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    enable_live_llm_tests: bool = False
    # Client-side pacing for Gemini calls (see app/llm_resilience.py).
    # Free tiers enforce a requests-per-minute cap; we pace under it rather
    # than discovering it via mid-batch 429s. 0 disables the limiter.
    llm_requests_per_minute: int = 15
    # Retry behavior for transient LLM errors (429/5xx/timeouts).
    llm_max_attempts: int = 3
    llm_backoff_base_seconds: float = 2.0
    # HMAC-SHA256 shared secret for verifying POST /webhooks/razorpay's
    # X-Razorpay-Signature header - matches how real Razorpay webhooks work.
    # Empty (the default) skips verification, so the demo doesn't require
    # provisioning a secret just to try the endpoint.
    razorpay_webhook_secret: str = ""
    # Opt-in per-merchant auth (see app/api/auth.py) - off by default to
    # keep judge/demo access frictionless, matching this project's existing
    # "no auth by default" stance for multi-tenancy.
    require_merchant_api_key: bool = False


settings = Settings()
