from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_dsn: str = "postgresql+asyncpg://vitalstream:vitalstream@localhost:5432/vitalstream"
    jwt_secret_key: str = "change-me-in-real-env"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    insight_service_base_url: str = "http://localhost:8003"
    config_service_base_url: str = "http://localhost:8002"


settings = Settings()
