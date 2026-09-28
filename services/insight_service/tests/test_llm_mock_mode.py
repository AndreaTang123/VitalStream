import pytest

from insight_service.llm_client import LLMClient
from insight_service.settings import settings


@pytest.fixture(autouse=True)
def _mock_mode():
    original = settings.llm_mode
    original_latency = settings.llm_mock_latency_seconds
    settings.llm_mode = "mock"
    settings.llm_mock_latency_seconds = 0.01  # keep the test fast
    yield
    settings.llm_mode = original
    settings.llm_mock_latency_seconds = original_latency


async def test_mock_mode_never_calls_a_real_client(monkeypatch):
    """week8: LLM_MODE=mock must short-circuit before touching AsyncOpenAI at
    all — a load test or CI run must be able to import/construct LLMClient
    with no OPENAI_API_KEY and never make a network call."""

    async def _fail_if_called(*args, **kwargs):
        raise AssertionError("real OpenAI client was called despite LLM_MODE=mock")

    client = LLMClient()
    monkeypatch.setattr(client._client.chat.completions, "create", _fail_if_called)

    response = await client.generate_insight({"heart_rate_mean": 72.0})

    assert response.content.startswith("[MOCK]")
    assert response.prompt_tokens > 0
    assert response.completion_tokens > 0
    assert response.cost_usd >= 0
