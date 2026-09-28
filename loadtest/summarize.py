"""week8 Step 10: turn benchmarks/raw/ingest_*.json (k6 --summary-export)
into the device-tier table for benchmarks/RESULTS.md — every number in that
table traces back to one of these files, not a hand-typed guess."""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "benchmarks" / "raw"


def main() -> None:
    paths = glob.glob(str(RAW_DIR / "ingest_*_run*.json"))

    def _key(path: str) -> tuple[int, int]:
        m = re.search(r"ingest_(\d+)_run(\d+)\.json", path)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    rows = []
    for path in sorted(paths, key=_key):
        m = re.search(r"ingest_(\d+)_run(\d+)\.json", path)
        if not m:
            continue
        devices, run = int(m.group(1)), int(m.group(2))
        d = json.load(open(path))
        metrics = d["metrics"]
        dur = metrics["http_req_duration"]
        failed = metrics["http_req_failed"]["value"]
        reqs = metrics["http_reqs"]["rate"]
        checks = metrics["checks"]
        rows.append(
            {
                "devices": devices,
                "run": run,
                "rps": reqs,
                "p50_ms": dur["p(50)"],
                "p95_ms": dur["p(95)"],
                "p99_ms": dur["p(99)"],
                "error_rate": failed,
                "checks_passed": checks["value"] == 1.0,
            }
        )

    print(f"{'devices':>7} {'run':>3} {'RPS':>9} {'P50ms':>8} {'P95ms':>8} {'P99ms':>8} {'err%':>7} {'SLO':>5}")
    for r in rows:
        slo_ok = r["p99_ms"] < 200 and r["error_rate"] < 0.01
        print(
            f"{r['devices']:>7} {r['run']:>3} {r['rps']:>9.1f} {r['p50_ms']:>8.2f} "
            f"{r['p95_ms']:>8.2f} {r['p99_ms']:>8.2f} {r['error_rate'] * 100:>6.2f}% "
            f"{'OK' if slo_ok else 'FAIL':>5}"
        )

    print("\nMarkdown table:\n")
    print("| Devices | RPS | Samples/s | P50 | P95 | P99 | Error rate | Stable? |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        slo_ok = r["p99_ms"] < 200 and r["error_rate"] < 0.01
        print(
            f"| {r['devices']} | {r['rps']:.1f} | {r['rps'] * 64:.0f} | {r['p50_ms']:.2f}ms | "
            f"{r['p95_ms']:.2f}ms | {r['p99_ms']:.2f}ms | {r['error_rate'] * 100:.2f}% | "
            f"{'✅' if slo_ok else '❌'} |"
        )


if __name__ == "__main__":
    main()
