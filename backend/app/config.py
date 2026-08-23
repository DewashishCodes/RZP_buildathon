from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://recovery:recovery@localhost:5432/revenue_recovery"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    enable_live_llm_tests: bool = False


settings = Settings()
