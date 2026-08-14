from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_dsn: str = "postgresql+asyncpg://vitalstream:vitalstream@localhost:5432/vitalstream"


settings = Settings()
