"""Windowed feature extraction over raw wearable signals (PRD 3.1).

Each function takes a window of raw values for a single signal type and
returns a scalar feature. `algo_version` on each function lets the consumer
loop (main.py) record which version produced a given `Feature` row, so gray
releases and rollbacks (config_service) are auditable.
"""

from __future__ import annotations

import numpy as np
from scipy import stats
from scipy.signal import butter, filtfilt, find_peaks

ALGO_VERSION_V1 = "v1"

# Bandpass range in Hz (36-150 bpm) and a per-window prominence threshold for
# find_peaks. Both were tuned against real PPG-DaLiA data, not guessed: a
# wider/higher band (e.g. up to 4 Hz / 240 bpm, the naive "human HR range")
# lets the dicrotic notch on the downslope of each PPG pulse register as its
# own peak, roughly doubling the detected peak count and the resulting bpm
# estimate — see services/feature_extraction/scripts/validate_ppg_dalia.py
# (week1-2-layer1-guide.md Step 6), which caught this via a ~37 bpm MAE
# against ground truth before it was tightened down to ~8 bpm.
_HR_BAND_LOW_HZ = 0.6  # 36 bpm
_HR_BAND_HIGH_HZ = 2.5  # 150 bpm
_PEAK_PROMINENCE_FRACTION = 0.4  # of the filtered window's stddev


def bandpass_filter_ppg(
    values: np.ndarray,
    sample_rate_hz: float,
    low_hz: float = _HR_BAND_LOW_HZ,
    high_hz: float = _HR_BAND_HIGH_HZ,
    order: int = 3,
) -> np.ndarray:
    """Zero-phase Butterworth bandpass isolating the cardiac component of a PPG signal."""
    if values.size == 0:
        raise ValueError("values window is empty")
    nyquist = sample_rate_hz / 2.0
    b, a = butter(order, [low_hz / nyquist, high_hz / nyquist], btype="band")
    padlen = 3 * (max(len(a), len(b)) - 1)
    if values.size <= padlen:
        raise ValueError(
            f"window of {values.size} samples too short to filtfilt (need > {padlen})"
        )
    return filtfilt(b, a, values)


def heart_rate_from_ppg(
    values: np.ndarray,
    sample_rate_hz: float,
    low_hz: float = _HR_BAND_LOW_HZ,
    high_hz: float = _HR_BAND_HIGH_HZ,
    prominence_fraction: float = _PEAK_PROMINENCE_FRACTION,
) -> float:
    """Instantaneous heart rate (bpm) from a raw PPG window via peak-interval detection.

    Bandpass-filters the window, finds systolic peaks at least one
    plausible-heartbeat apart, and returns 60 / mean(peak-to-peak interval).
    `low_hz`/`high_hz`/`prominence_fraction` default to the tuned v1 values
    but are parameterized so a second, deliberately worse version can reuse
    this exact implementation (see heart_rate_from_ppg_v2_naive below)
    instead of duplicating it.
    """
    filtered = bandpass_filter_ppg(values, sample_rate_hz, low_hz, high_hz)
    # Minimum samples between peaks at the fastest plausible heart rate (high_hz).
    min_distance_samples = max(int(sample_rate_hz / high_hz), 1)
    peaks, _ = find_peaks(
        filtered,
        distance=min_distance_samples,
        prominence=prominence_fraction * float(np.std(filtered)),
    )
    if peaks.size < 2:
        raise ValueError("not enough peaks detected to compute a heart rate")

    peak_intervals_s = np.diff(peaks) / sample_rate_hz
    mean_interval_s = float(np.mean(peak_intervals_s))
    return 60.0 / mean_interval_s


ALGO_VERSION_V2_NAIVE = "v2-naive-wideband"


def heart_rate_from_ppg_v2_naive(values: np.ndarray, sample_rate_hz: float) -> float:
    """A real, reproducible "bad" version for week3-layer1-deepening-guide.md
    Step 3/4's gray-release demo — not a synthetic placeholder. These are
    literally the pre-tuning parameters from week1-2-layer1-guide.md Step 6:
    a wider 0.5-4 Hz band with no peak-prominence filter, which lets each PPG
    pulse's dicrotic notch register as its own peak. Measured ~37 bpm MAE
    against PPG-DaLiA ground truth, vs ~8 bpm for heart_rate_from_ppg's
    tuned defaults (see scripts/validate_ppg_dalia.py).
    """
    return heart_rate_from_ppg(values, sample_rate_hz, low_hz=0.5, high_hz=4.0, prominence_fraction=0.0)


HEART_RATE_ALGORITHMS = {
    ALGO_VERSION_V1: heart_rate_from_ppg,
    ALGO_VERSION_V2_NAIVE: heart_rate_from_ppg_v2_naive,
}


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
