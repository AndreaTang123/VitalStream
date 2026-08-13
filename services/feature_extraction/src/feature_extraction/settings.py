from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka_bootstrap_servers: str = "localhost:29092"
    raw_signals_topic: str = "raw-signals"
    features_topic: str = "features"
    consumer_group_id: str = "feature-extraction"
    config_service_base_url: str = "http://localhost:8002"
    # Plain Postgres for the `features` table (week1-2-layer1-guide.md Step 7).
    postgres_dsn: str = "postgresql+asyncpg://vitalstream:vitalstream@localhost:5432/vitalstream"
    # TimescaleDB hypertable for raw signal storage — Week 3+ (PRD 4.1), unused for now.
    timescale_dsn: str = "postgresql+asyncpg://vitalstream:vitalstream@localhost:5433/vitalstream_timeseries"


settings = Settings()
