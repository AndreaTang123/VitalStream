from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kafka_bootstrap_servers: str = "localhost:29092"
    raw_signals_topic: str = "raw-signals"
    kafka_batch_size: int = 100
    kafka_linger_ms: int = 20


settings = Settings()
