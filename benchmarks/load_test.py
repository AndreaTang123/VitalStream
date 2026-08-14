"""Fixed-concurrency load test against ingestion's signal-batch endpoint
(week3-layer1-deepening-guide.md Step 1/6).

Used twice: once against the pre-optimization baseline (plain asyncio event
loop, unwired batch-size config) and once after Step 6's uvloop + batching
changes, so the improvement is a measured before/after rather than a guess.
No external tool (hey/locust) needed — a handful of concurrent httpx workers
hammering the endpoint for a fixed duration is enough to get real P50/P99/RPS.

Usage:
    python benchmarks/load_test.py --concurrency 20 --duration 30 \\
        --label "baseline (asyncio loop)" >> benchmarks/baseline.md
"""

from __future__ import annotations

import argparse
import asyncio
import time
from uuid import uuid4

import httpx

SAMPLE_RATE_HZ = 64.0
CHUNK_SECONDS = 1.0


def _payload() -> dict:
    return {
        "signal_type": "ppg",
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "start_ts": time.time(),
        "values": [0.0] * int(SAMPLE_RATE_HZ * CHUNK_SECONDS),
    }


async def _worker(
    client: httpx.AsyncClient, device_id: str, deadline: float, latencies_ms: list[float]
) -> None:
    while time.monotonic() < deadline:
        start = time.monotonic()
        try:
            response = await client.post(f"/api/v1/devices/{device_id}/signals", json=_payload())
            response.raise_for_status()
        except httpx.HTTPError:
            continue  # dropped/failed request — not counted as a latency sample
        latencies_ms.append((time.monotonic() - start) * 1000)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return float("nan")
    idx = min(int(len(sorted_values) * pct), len(sorted_values) - 1)
    return sorted_values[idx]


async def run(url: str, concurrency: int, duration: float) -> dict:
    latencies_ms: list[float] = []
    deadline = time.monotonic() + duration

    # Default httpx limits cap keepalive connections at 20 — with more
    # concurrent workers than that sharing one client, most requests pay a
    # fresh TCP handshake instead of reusing a connection, which swamps
    # whatever the benchmark is actually trying to measure server-side.
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(base_url=url, timeout=10.0, limits=limits) as client:
        device_ids = [str(uuid4()) for _ in range(concurrency)]
        started = time.monotonic()
        await asyncio.gather(
            *[_worker(client, device_id, deadline, latencies_ms) for device_id in device_ids]
        )
        elapsed = time.monotonic() - started

    latencies_ms.sort()
    return {
        "requests": len(latencies_ms),
        "elapsed_s": elapsed,
        "rps": len(latencies_ms) / elapsed if elapsed > 0 else 0.0,
        "p50_ms": _percentile(latencies_ms, 0.50),
        "p95_ms": _percentile(latencies_ms, 0.95),
        "p99_ms": _percentile(latencies_ms, 0.99),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8001")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--label", default=None, help="tag printed with the results, e.g. 'baseline'")
    args = parser.parse_args()

    result = asyncio.run(run(args.url, args.concurrency, args.duration))

    label = f" [{args.label}]" if args.label else ""
    print(f"### load test{label} — concurrency={args.concurrency} duration={args.duration}s")
    print(f"- requests: {result['requests']} in {result['elapsed_s']:.1f}s")
    print(f"- RPS: {result['rps']:.1f}")
    print(f"- P50: {result['p50_ms']:.2f} ms")
    print(f"- P95: {result['p95_ms']:.2f} ms")
    print(f"- P99: {result['p99_ms']:.2f} ms")


if __name__ == "__main__":
    main()
