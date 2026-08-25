from insight_service.cache import cache_key, make_cache_key


def test_cache_key_is_deterministic():
    key_a = cache_key("user-1", {"resting_heart_rate": 55.0}, "gpt-4o-mini", "v1")
    key_b = cache_key("user-1", {"resting_heart_rate": 55.0}, "gpt-4o-mini", "v1")
    assert key_a == key_b


def test_cache_key_differs_by_prompt_version():
    key_v1 = cache_key("user-1", {"resting_heart_rate": 55.0}, "gpt-4o-mini", "v1")
    key_v2 = cache_key("user-1", {"resting_heart_rate": 55.0}, "gpt-4o-mini", "v2")
    assert key_v1 != key_v2


# --- make_cache_key: the autonomous device-insight pipeline's normalized key ---


def test_make_cache_key_ignores_float_noise():
    """week4-layer2-milestone-guide.md Step 8: 72.001 vs 72.002 must not
    produce different keys, or real-world cache hit rate would be ~0."""
    key_a = make_cache_key({"heart_rate_mean": 72.001, "heart_rate_trend": 1.0}, "v1", "gpt-4o-mini")
    key_b = make_cache_key({"heart_rate_mean": 72.002, "heart_rate_trend": 1.0}, "v1", "gpt-4o-mini")
    assert key_a == key_b


def test_make_cache_key_differs_on_meaningfully_different_values():
    key_a = make_cache_key({"heart_rate_mean": 72.0}, "v1", "gpt-4o-mini")
    key_b = make_cache_key({"heart_rate_mean": 90.0}, "v1", "gpt-4o-mini")
    assert key_a != key_b


def test_make_cache_key_differs_by_prompt_version():
    key_v1 = make_cache_key({"heart_rate_mean": 72.0}, "v1", "gpt-4o-mini")
    key_v2 = make_cache_key({"heart_rate_mean": 72.0}, "v2", "gpt-4o-mini")
    assert key_v1 != key_v2


def test_make_cache_key_differs_by_model():
    key_a = make_cache_key({"heart_rate_mean": 72.0}, "v1", "gpt-4o-mini")
    key_b = make_cache_key({"heart_rate_mean": 72.0}, "v1", "gpt-4o")
    assert key_a != key_b


def test_make_cache_key_ignores_key_order():
    key_a = make_cache_key({"heart_rate_mean": 72.0, "heart_rate_trend": 1.0}, "v1", "gpt-4o-mini")
    key_b = make_cache_key({"heart_rate_trend": 1.0, "heart_rate_mean": 72.0}, "v1", "gpt-4o-mini")
    assert key_a == key_b
