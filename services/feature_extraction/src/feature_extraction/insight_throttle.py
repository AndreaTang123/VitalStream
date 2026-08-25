"""Insight-request throttling + snapshot aggregation (week4-layer2-milestone-guide.md Step 2).

Pure functions, deliberately kept separate from the Kafka/consumer plumbing
in main.py so "when do we publish" and "how do we aggregate" are unit
testable without a running broker (Step 8) — the same split main.py already
uses for features.py's signal-processing functions.
"""

from __future__ import annotations

from collections.abc import Sequence


def should_publish_insight(now: float, last_insight_ts: float | None, throttle_seconds: float) -> bool:
    """True if enough device-time has passed since the last InsightRequest
    for this device. `now` is the triggering window's `window_end`, not
    wall-clock time — throttling is about how much of the *signal* has
    accumulated, and staying wall-clock-free keeps this reproducible
    regardless of simulator playback speed."""
    if last_insight_ts is None:
        return True
    return (now - last_insight_ts) >= throttle_seconds


def aggregate_snapshot(recent_values: Sequence[float]) -> dict[str, float]:
    """Collapse the last N heart-rate windows into one snapshot: mean level +
    first-to-last trend (week4-layer2-milestone-guide.md Step 2: "简单聚合
    即可：均值 + 首尾差值当趋势"). A single window is too little signal for a
    non-generic insight — this is why InsightRequest carries an aggregate,
    not a raw Feature."""
    if not recent_values:
        raise ValueError("recent_values must be non-empty")
    mean = sum(recent_values) / len(recent_values)
    trend = recent_values[-1] - recent_values[0]
    return {
        "heart_rate_mean": mean,
        "heart_rate_trend": trend,
        "window_count": float(len(recent_values)),
    }
