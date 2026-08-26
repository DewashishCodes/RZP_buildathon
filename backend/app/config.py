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


settings = Settings()
