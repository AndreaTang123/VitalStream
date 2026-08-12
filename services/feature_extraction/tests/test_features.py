import numpy as np
import pytest

from feature_extraction.features import hrv_rmssd, resting_heart_rate, sleep_quality_score


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
