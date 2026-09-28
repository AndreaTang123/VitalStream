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

    # week5-layer2-deepening-guide.md Step 3: same model as generation by
    # default (cheap), but configurable to a different one to reduce
    # "grading its own homework" bias.
    judge_model_name: str = "gpt-4o-mini"
    judge_timeout_seconds: float = 15.0

    # week8 Step 1: no HTTP server of its own for the consumer, so /metrics
    # gets its own port via prometheus_client.start_http_server.
    metrics_port: int = 9102

    # week8: "LLM_MODE=mock" for load testing and CI — real numbers
    # (grounded_rate, hallucination_rate, cache hit rate, $ saved) all come
    # from Week 5's real-OpenAI runs (benchmarks/week5_eval_report.md) and
    # are never re-measured against the mock. Mock mode exists so load
    # testing doesn't burn real API spend and CI doesn't need a real key.
    llm_mode: str = "real"
    llm_mock_latency_seconds: float = 0.8



settings = Settings()
