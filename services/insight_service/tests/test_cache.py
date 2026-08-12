from insight_service.cache import cache_key


def test_cache_key_is_deterministic():
    key_a = cache_key("user-1", {"resting_heart_rate": 55.0}, "gpt-4o-mini", "v1")
    key_b = cache_key("user-1", {"resting_heart_rate": 55.0}, "gpt-4o-mini", "v1")
    assert key_a == key_b


def test_cache_key_differs_by_prompt_version():
    key_v1 = cache_key("user-1", {"resting_heart_rate": 55.0}, "gpt-4o-mini", "v1")
    key_v2 = cache_key("user-1", {"resting_heart_rate": 55.0}, "gpt-4o-mini", "v2")
    assert key_v1 != key_v2
