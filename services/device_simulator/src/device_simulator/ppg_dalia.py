"""Loads a PPG-DaLiA subject recording (week1-2-layer1-guide.md Step 3).

Field names confirmed by actually loading a subject file rather than
guessing (the dataset's own convention warns per-release naming can drift):
each `S<N>/S<N>.pkl` is a dict with `signal.wrist.BVP` (64Hz Empatica E4
photoplethysmogram, shape (N, 1)) and `label` (ground-truth heart rate, one
value per 8s-window/2s-step, matching feature_extraction's own windowing).
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

BVP_SAMPLE_RATE_HZ = 64.0
LABEL_WINDOW_SECONDS = 8.0
LABEL_STEP_SECONDS = 2.0


def subject_pkl_path(data_dir: Path, subject: str) -> Path:
    return data_dir / subject / f"{subject}.pkl"


def load_subject(data_dir: Path, subject: str) -> dict:
    with subject_pkl_path(data_dir, subject).open("rb") as f:
        return pickle.load(f, encoding="latin1")


def load_wrist_bvp(data_dir: Path, subject: str) -> np.ndarray:
    """1D array of raw wrist BVP samples at BVP_SAMPLE_RATE_HZ."""
    data = load_subject(data_dir, subject)
    return data["signal"]["wrist"]["BVP"].reshape(-1)


def load_ground_truth_hr(data_dir: Path, subject: str) -> np.ndarray:
    """1D array of ground-truth HR labels, one per (LABEL_WINDOW_SECONDS, LABEL_STEP_SECONDS) window."""
    data = load_subject(data_dir, subject)
    return data["label"].reshape(-1)


def default_data_dir() -> Path:
    # .../services/device_simulator/src/device_simulator/ppg_dalia.py -> repo root
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "data" / "raw" / "ppg_dalia" / "PPG_FieldStudy"
