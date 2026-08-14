"""Offline validation of the PPG->heart-rate algorithm against PPG-DaLiA's own
ground-truth HR labels (week1-2-layer1-guide.md Step 6).

Not part of the running pipeline: a standalone script to get a real MAE
number and catch peak-detection problems before trusting the algorithm
end-to-end. Reuses feature_extraction's actual heart_rate_from_ppg() and its
windowing constants, so this validates exactly what the live consumer runs.

Usage (from repo root, using feature_extraction's venv):
    services/feature_extraction/.venv/bin/python \\
        services/feature_extraction/scripts/validate_ppg_dalia.py --subject S2 --plot
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np

from feature_extraction.features import HEART_RATE_ALGORITHMS
from feature_extraction.main import STEP_SECONDS, WINDOW_SECONDS

BVP_SAMPLE_RATE_HZ = 64.0


def load_subject(data_dir: Path, subject: str) -> dict:
    with (data_dir / subject / f"{subject}.pkl").open("rb") as f:
        return pickle.load(f, encoding="latin1")


def estimate_hr_series(bvp: np.ndarray, n_windows: int, algo_version: str) -> np.ndarray:
    """One heart-rate estimate per ground-truth window, aligned to PPG-DaLiA's
    own (WINDOW_SECONDS, STEP_SECONDS) convention starting at t=0."""
    algo_fn = HEART_RATE_ALGORITHMS[algo_version]
    window_samples = int(WINDOW_SECONDS * BVP_SAMPLE_RATE_HZ)
    step_samples = int(STEP_SECONDS * BVP_SAMPLE_RATE_HZ)
    estimates = np.full(n_windows, np.nan)

    for i in range(n_windows):
        start = i * step_samples
        window = bvp[start : start + window_samples]
        if len(window) < window_samples:
            break
        try:
            estimates[i] = algo_fn(window, BVP_SAMPLE_RATE_HZ)
        except ValueError:
            continue  # not enough peaks in this window — leave as NaN, counted against coverage

    return estimates


def _default_data_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "data" / "raw" / "ppg_dalia" / "PPG_FieldStudy"


def _save_plot(subject: str, ground_truth: np.ndarray, estimates: np.ndarray) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed — skipping plot (pip install matplotlib)")
        return

    x = np.arange(len(ground_truth)) * STEP_SECONDS
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(x, ground_truth, label="ground truth")
    ax.plot(x, estimates, label="estimate", alpha=0.7)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("heart rate (bpm)")
    ax.set_title(f"{subject}: estimated vs ground-truth heart rate")
    ax.legend()

    out_path = Path(f"{subject}_hr_validation.png")
    fig.savefig(out_path, dpi=120)
    print(f"saved plot to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="S2")
    parser.add_argument("--data-dir", default=None, help="defaults to <repo root>/data/raw/ppg_dalia/PPG_FieldStudy")
    parser.add_argument(
        "--algo-version",
        default="v1",
        choices=sorted(HEART_RATE_ALGORITHMS),
        help="which HEART_RATE_ALGORITHMS entry to validate — e.g. v2-naive-wideband "
        "reproduces the week3 gray-release demo's deliberately-bad canary",
    )
    parser.add_argument("--plot", action="store_true", help="save an estimate-vs-ground-truth PNG")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else _default_data_dir()
    data = load_subject(data_dir, args.subject)
    bvp = data["signal"]["wrist"]["BVP"].reshape(-1)
    ground_truth = data["label"].reshape(-1)

    estimates = estimate_hr_series(bvp, n_windows=len(ground_truth), algo_version=args.algo_version)
    valid = ~np.isnan(estimates)
    mae = float(np.mean(np.abs(estimates[valid] - ground_truth[valid])))
    coverage = valid.sum() / len(ground_truth)

    print(f"subject={args.subject} algo_version={args.algo_version} windows={len(ground_truth)} coverage={coverage:.1%}")
    print(f"MAE = {mae:.2f} bpm")

    if args.plot:
        _save_plot(args.subject, ground_truth, estimates)


if __name__ == "__main__":
    main()
