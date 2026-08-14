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


settings = Settings()
