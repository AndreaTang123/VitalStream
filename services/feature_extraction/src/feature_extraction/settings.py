from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka_bootstrap_servers: str = "localhost:29092"
    raw_signals_topic: str = "raw-signals"
    features_topic: str = "features"
    consumer_group_id: str = "feature-extraction"
    config_service_base_url: str = "http://localhost:8002"
    timescale_dsn: str = "postgresql+asyncpg://vitalstream:vitalstream@localhost:5433/vitalstream_timeseries"


settings = Settings()
