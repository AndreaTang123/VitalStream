from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    llm_model_name: str = "gpt-4o-mini"
    prompt_version: str = "v1"
    redis_url: str = "redis://localhost:6379/0"
    insight_cache_ttl_seconds: int = 3600


settings = Settings()
