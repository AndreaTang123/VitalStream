from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_dsn: str = "postgresql+asyncpg://vitalstream:vitalstream@localhost:5432/vitalstream"
    jwt_secret_key: str = "change-me-in-real-env"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    insight_service_base_url: str = "http://localhost:8003"
    config_service_base_url: str = "http://localhost:8002"
    # Local frontend origins only (Week 7) — never "*" for an API that sets
    # bearer tokens from patient/coach browsers.
    cors_allow_origins: list[str] = ["http://localhost:3000"]
    # Fixed-window login rate limit (PRD 5.3's "basic throttling", not a full
    # Redis-backed limiter — single-process is an accepted tradeoff at this
    # project's scale; see README "认证与权限").
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 60


settings = Settings()
