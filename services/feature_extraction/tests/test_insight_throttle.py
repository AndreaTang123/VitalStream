import pytest

from feature_extraction.insight_throttle import aggregate_snapshot, should_publish_insight


def test_should_publish_when_never_published_before():
    assert should_publish_insight(now=100.0, last_insight_ts=None, throttle_seconds=60.0) is True


def test_should_not_publish_within_throttle_window():
    assert should_publish_insight(now=100.0, last_insight_ts=50.0, throttle_seconds=60.0) is False


def test_should_publish_once_throttle_window_elapses():
    assert should_publish_insight(now=110.0, last_insight_ts=50.0, throttle_seconds=60.0) is True


def test_throttle_over_a_sequence_of_windows_only_fires_periodically():
    """Mirrors how main.py actually calls this: once per emitted window,
    with window_end advancing by STEP_SECONDS=2.0 each time."""
    last_ts = None
    fired_at = []
    for window_end in [t * 2.0 for t in range(1, 51)]:  # 2s, 4s, ... 100s
        if should_publish_insight(window_end, last_ts, throttle_seconds=10.0):
            fired_at.append(window_end)
            last_ts = window_end

    assert fired_at == [2.0, 12.0, 22.0, 32.0, 42.0, 52.0, 62.0, 72.0, 82.0, 92.0]


def test_aggregate_snapshot_mean_and_trend():
    snapshot = aggregate_snapshot([70.0, 72.0, 74.0, 76.0])
    assert snapshot == {"heart_rate_mean": 73.0, "heart_rate_trend": 6.0, "window_count": 4.0}


def test_aggregate_snapshot_rejects_empty():
    with pytest.raises(ValueError):
        aggregate_snapshot([])
