from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://recovery:recovery@localhost:5432/revenue_recovery"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    enable_live_llm_tests: bool = False


settings = Settings()
