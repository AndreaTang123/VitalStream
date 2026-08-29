"""Cache-savings report (week5-layer2-deepening-guide.md Step 6): from the
last N device_insights rows, how many LLM calls did the cache avoid, what
did that save in $ (at the average cost of the calls that DID happen), and
what's the average latency delta? This is PRD 8's "缓存命中率带来的成本/延迟
节省比例" metric computed from real production rows, not the benchmark set —
Week 4 only proved the caching mechanism existed; this is where the number
it actually produces gets measured.

Usage:
    python -m insight_service.eval.cache_savings --limit 200
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from insight_service.db import DeviceInsightORM
from insight_service.settings import settings


async def compute_savings(limit: int) -> dict:
    engine = create_async_engine(settings.postgres_dsn)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                select(DeviceInsightORM).order_by(DeviceInsightORM.generated_at.desc()).limit(limit)
            )
            rows = result.all()
    finally:
        await engine.dispose()

    if not rows:
        return {"n": 0}

    hits = [r for r in rows if r.cache_hit]
    misses = [r for r in rows if not r.cache_hit]
    n = len(rows)

    avg_miss_cost_usd = sum(r.cost_usd for r in misses) / len(misses) if misses else 0.0
    avg_hit_latency_ms = sum(r.latency_ms for r in hits) / len(hits) if hits else 0.0
    avg_miss_latency_ms = sum(r.latency_ms for r in misses) / len(misses) if misses else 0.0

    return {
        "n": n,
        "hits": len(hits),
        "misses": len(misses),
        "hit_rate": len(hits) / n,
        "avg_miss_cost_usd": avg_miss_cost_usd,
        # Every hit stood in for what would otherwise have been a call at
        # the miss-population's average cost — that's the "saved" spend.
        "estimated_savings_usd": len(hits) * avg_miss_cost_usd,
        "avg_hit_latency_ms": avg_hit_latency_ms,
        "avg_miss_latency_ms": avg_miss_latency_ms,
        "latency_delta_ms": avg_miss_latency_ms - avg_hit_latency_ms,
    }


def print_report(stats: dict) -> None:
    if stats.get("n", 0) == 0:
        print("no device_insights rows found")
        return

    print(f"=== cache savings, last {stats['n']} device_insights rows ===")
    print(f"hits:   {stats['hits']}")
    print(f"misses: {stats['misses']}")
    print(f"hit_rate: {stats['hit_rate']:.1%}")
    print(f"avg cost per real LLM call: ${stats['avg_miss_cost_usd']:.6f}")
    print(f"avg latency: hit={stats['avg_hit_latency_ms']:.1f}ms  miss={stats['avg_miss_latency_ms']:.1f}ms")
    print()
    print(
        f"缓存命中率 {stats['hit_rate']:.1%}，按当前 LLM 单价折算，"
        f"相当于节省了约 ${stats['estimated_savings_usd']:.6f} / "
        f"降低了 {stats['latency_delta_ms']:.1f} ms 平均延迟"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    stats = asyncio.run(compute_savings(args.limit))
    print_report(stats)


if __name__ == "__main__":
    main()
