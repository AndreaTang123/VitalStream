from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka_bootstrap_servers: str = "localhost:29092"
    raw_signals_topic: str = "raw-signals"
    # aiokafka's max_batch_size is bytes-per-partition-batch, not a message
    # count — the old `kafka_batch_size = 100` field was never actually wired
    # into AIOKafkaProducer (week3-layer1-deepening-guide.md Step 6 caught
    # this) and, read as bytes, 100 would have been smaller than a single
    # message anyway. Default here is 4x aiokafka's own default (16384).
    kafka_max_batch_size_bytes: int = 65536
    kafka_linger_ms: int = 20

    # Week 6/Layer 3 (PRD 4.5): this endpoint is called by devices/the
    # simulator, not a logged-in browser, so it's gated by a static shared
    # secret rather than a user JWT — a device has no "login".
    service_token: str = "change-me-in-real-env"
    postgres_dsn: str = "postgresql://vitalstream:vitalstream@localhost:5432/vitalstream"
    device_registry_refresh_seconds: float = 30.0


settings = Settings()
