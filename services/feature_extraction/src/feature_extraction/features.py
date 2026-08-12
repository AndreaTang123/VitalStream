"""Windowed feature extraction over raw wearable signals (PRD 3.1).

Each function takes a window of raw values for a single signal type and
returns a scalar feature. `algo_version` on each function lets the consumer
loop (main.py) record which version produced a given `Feature` row, so gray
releases and rollbacks (config_service) are auditable.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

ALGO_VERSION_V1 = "v1"


def resting_heart_rate(heart_rate_bpm: np.ndarray, low_percentile: float = 10.0) -> float:
    """Resting HR proxy: the low-percentile of HR samples in the window."""
    if heart_rate_bpm.size == 0:
        raise ValueError("heart_rate_bpm window is empty")
    return float(np.percentile(heart_rate_bpm, low_percentile))


def hrv_rmssd(rr_intervals_ms: np.ndarray) -> float:
    """Root mean square of successive differences between RR intervals."""
    if rr_intervals_ms.size < 2:
        raise ValueError("need at least 2 RR intervals to compute RMSSD")
    diffs = np.diff(rr_intervals_ms)
    return float(np.sqrt(np.mean(diffs**2)))


def hrv_trend(rmssd_window: np.ndarray) -> float:
    """Linear trend (slope) of RMSSD over a sequence of prior windows."""
    if rmssd_window.size < 2:
        raise ValueError("need at least 2 RMSSD samples to compute a trend")
    x = np.arange(rmssd_window.size)
    slope, _intercept, _r, _p, _stderr = stats.linregress(x, rmssd_window)
    return float(slope)


def sleep_quality_score(stage_minutes: dict[str, float]) -> float:
    """Weighted sleep quality score in [0, 1] from time-in-stage minutes.

    Deep and REM sleep are weighted higher than light sleep; awake time
    counts against the score.
    """
    weights = {"deep": 1.0, "rem": 0.8, "light": 0.4, "awake": -0.5}
    total_minutes = sum(stage_minutes.values())
    if total_minutes <= 0:
        raise ValueError("stage_minutes must sum to a positive duration")

    weighted = sum(weights.get(stage, 0.0) * minutes for stage, minutes in stage_minutes.items())
    max_possible = weights["deep"] * total_minutes
    return float(np.clip(weighted / max_possible, 0.0, 1.0))
