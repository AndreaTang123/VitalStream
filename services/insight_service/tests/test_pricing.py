from insight_service.pricing import calculate_cost_usd


def test_calculate_cost_usd_known_rate():
    # gpt-4o-mini: $0.00015/1k input, $0.00060/1k output (pricing.py)
    cost = calculate_cost_usd("gpt-4o-mini", prompt_tokens=1000, completion_tokens=1000)
    assert cost == 0.00015 + 0.00060


def test_calculate_cost_usd_scales_linearly_with_tokens():
    cost_500 = calculate_cost_usd("gpt-4o-mini", prompt_tokens=500, completion_tokens=0)
    cost_1000 = calculate_cost_usd("gpt-4o-mini", prompt_tokens=1000, completion_tokens=0)
    assert cost_1000 == cost_500 * 2


def test_calculate_cost_usd_differs_by_model():
    mini_cost = calculate_cost_usd("gpt-4o-mini", prompt_tokens=1000, completion_tokens=1000)
    full_cost = calculate_cost_usd("gpt-4o", prompt_tokens=1000, completion_tokens=1000)
    assert full_cost > mini_cost


def test_calculate_cost_usd_falls_back_for_unknown_model():
    # doesn't crash, and doesn't silently return $0 for an unrecognized model
    cost = calculate_cost_usd("some-future-model", prompt_tokens=1000, completion_tokens=1000)
    assert cost > 0


def test_calculate_cost_usd_zero_tokens_is_zero_cost():
    assert calculate_cost_usd("gpt-4o-mini", prompt_tokens=0, completion_tokens=0) == 0.0
