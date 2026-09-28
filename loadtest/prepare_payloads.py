"""week8 Step 3: slice a real PPG-DaLiA subject into 1-second (64-sample)
chunks for k6 to replay — real wearable data, not `Math.random()`, per the
PRD risk table's own "缺乏真实设备数据，压测结果不可信" entry.

Reuses device_simulator's loader rather than re-implementing PPG-DaLiA's
pickle format here. Run with device_simulator's venv (has numpy + the
dataset loader):

    services/device_simulator/.venv/bin/python loadtest/prepare_payloads.py

Output: loadtest/data/ppg_chunks.json — a flat JSON array of 64-float
arrays. k6 loads it once via SharedArray and cycles through it; the exact
values don't need to line up with any particular subject's ground truth for
a load test (unlike validate_ppg_dalia.py's accuracy check) — they just
need to be real signal shape, not synthetic noise, so the bandpass filter +
peak detector in feature_extraction does real (not trivially fast/slow)
work per window.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from device_simulator.ppg_dalia import BVP_SAMPLE_RATE_HZ, default_data_dir, load_wrist_bvp

CHUNK_SAMPLES = int(BVP_SAMPLE_RATE_HZ)  # 64 samples = 1 second at 64Hz


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="S2")
    parser.add_argument("--chunks", type=int, default=5000, help="how many 1s chunks to export")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else default_data_dir()
    out_path = Path(args.out) if args.out else Path(__file__).parent / "data" / "ppg_chunks.json"

    bvp = load_wrist_bvp(data_dir, args.subject)
    total_available = len(bvp) // CHUNK_SAMPLES
    n_chunks = min(args.chunks, total_available)

    chunks = [
        bvp[i * CHUNK_SAMPLES : (i + 1) * CHUNK_SAMPLES].tolist() for i in range(n_chunks)
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(chunks))
    print(f"wrote {n_chunks} chunks ({n_chunks * CHUNK_SAMPLES} samples) from subject {args.subject} -> {out_path}")


if __name__ == "__main__":
    main()
