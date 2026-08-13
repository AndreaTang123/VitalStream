import numpy as np
import pytest

from feature_extraction.features import (
    heart_rate_from_ppg,
    hrv_rmssd,
    resting_heart_rate,
    sleep_quality_score,
)


def _synthetic_ppg(bpm: float, duration_s: float = 8.0, fs: float = 64.0, seed: int = 0) -> np.ndarray:
    t = np.arange(0, duration_s, 1 / fs)
    freq_hz = bpm / 60.0
    noise = 0.05 * np.random.default_rng(seed).standard_normal(t.size)
    return np.sin(2 * np.pi * freq_hz * t) + 0.3 * np.sin(2 * np.pi * 2 * freq_hz * t) + noise


@pytest.mark.parametrize("bpm", [50.0, 72.0, 110.0])
def test_heart_rate_from_ppg_recovers_known_bpm(bpm):
    estimate = heart_rate_from_ppg(_synthetic_ppg(bpm), sample_rate_hz=64.0)
    assert estimate == pytest.approx(bpm, abs=3.0)


def test_heart_rate_from_ppg_rejects_too_short_window():
    with pytest.raises(ValueError):
        heart_rate_from_ppg(np.array([0.1, 0.2, 0.3]), sample_rate_hz=64.0)


def test_resting_heart_rate_uses_low_percentile():
    hr = np.array([60, 62, 58, 90, 95, 100, 61, 59])
    assert resting_heart_rate(hr, low_percentile=25.0) < 62


def test_resting_heart_rate_rejects_empty_window():
    with pytest.raises(ValueError):
        resting_heart_rate(np.array([]))


def test_hrv_rmssd_known_value():
    rr = np.array([800.0, 810.0, 790.0, 805.0])
    result = hrv_rmssd(rr)
    assert result == pytest.approx(np.sqrt(np.mean(np.diff(rr) ** 2)))


def test_sleep_quality_score_prefers_deep_and_rem():
    good_night = sleep_quality_score({"deep": 90, "rem": 60, "light": 120, "awake": 10})
    bad_night = sleep_quality_score({"deep": 10, "rem": 10, "light": 60, "awake": 90})
    assert good_night > bad_night


def test_sleep_quality_score_rejects_zero_duration():
    with pytest.raises(ValueError):
        sleep_quality_score({"deep": 0, "rem": 0})
