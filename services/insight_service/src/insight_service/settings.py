from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    llm_model_name: str = "gpt-4o-mini"
    prompt_version: str = "v1"
    redis_url: str = "redis://localhost:6379/0"
    insight_cache_ttl_seconds: int = 3600
    llm_timeout_seconds: float = 15.0

    # week4-layer2-milestone-guide.md Step 3+: the autonomous consumer half
    # of this service, decoupled from the on-demand `/insights/generate`
    # HTTP endpoint above (different trigger, different Postgres table).
    kafka_bootstrap_servers: str = "localhost:29092"
    features_extracted_topic: str = "features-extracted"
    consumer_group_id: str = "insight-generator"
    postgres_dsn: str = "postgresql+asyncpg://vitalstream:vitalstream@localhost:5432/vitalstream"


settings = Settings()
