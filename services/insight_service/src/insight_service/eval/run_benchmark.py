"""Offline benchmark runner (week5-layer2-deepening-guide.md Step 4): for
each case in benchmarks/cases.yaml, calls the real LLM directly — bypassing
Redis on purpose, since eval wants to measure real generation quality, not
whether the cache was warm — runs both judge dimensions, and writes one row
per case to benchmarks/results/{timestamp}_{prompt_version}_{model}.csv.

Usage:
    python -m insight_service.eval.run_benchmark --prompt-version v1 --model gpt-4o-mini
    python -m insight_service.eval.run_benchmark --prompt-version v2 --model gpt-4o-mini
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import time
from pathlib import Path

import yaml
from vitalstream_common.schemas import BenchmarkCase, EvalResult

from insight_service.eval.judge import check_grounded, hallucination_judge
from insight_service.llm_client import llm_client

CSV_FIELDS = [
    "case_id", "category", "prompt_version", "model", "grounded",
    "hallucination_flag", "judge_notes", "latency_ms", "prompt_tokens",
    "completion_tokens", "cost_usd", "insight_text",
]


def load_cases(path: Path) -> list[BenchmarkCase]:
    raw = yaml.safe_load(path.read_text())
    return [BenchmarkCase(**item) for item in raw]


async def run_case(case: BenchmarkCase, prompt_version: str, model: str) -> EvalResult:
    response = await llm_client.generate_device_insight(
        case.feature_snapshot, prompt_version=prompt_version, model_version=model
    )
    grounded = check_grounded(response.content, case.feature_snapshot)
    hallucination_flag, judge_notes = await hallucination_judge.check_hallucination(response.content)

    return EvalResult(
        case_id=case.case_id,
        prompt_version=prompt_version,
        model=model,
        insight_text=response.content,
        grounded=grounded,
        hallucination_flag=hallucination_flag,
        judge_notes=judge_notes,
        latency_ms=response.latency_ms,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        cost_usd=response.cost_usd,
    )


async def run_benchmark(
    cases: list[BenchmarkCase], prompt_version: str, model: str
) -> list[tuple[BenchmarkCase, EvalResult]]:
    rows: list[tuple[BenchmarkCase, EvalResult]] = []
    for case in cases:
        try:
            result = await run_case(case, prompt_version, model)
        except Exception as exc:  # noqa: BLE001 - one bad case shouldn't abort the whole run
            print(f"  ! {case.case_id} failed, skipping: {exc}")
            continue
        rows.append((case, result))
        print(
            f"  {case.case_id:16s} grounded={result.grounded!s:5s} "
            f"hallucination={result.hallucination_flag!s:5s} "
            f"latency={result.latency_ms:6.0f}ms cost=${result.cost_usd:.6f}"
        )
    return rows


def write_csv(rows: list[tuple[BenchmarkCase, EvalResult]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for case, result in rows:
            writer.writerow(
                {
                    "case_id": result.case_id,
                    "category": case.category,
                    "prompt_version": result.prompt_version,
                    "model": result.model,
                    "grounded": result.grounded,
                    "hallucination_flag": result.hallucination_flag,
                    "judge_notes": result.judge_notes,
                    "latency_ms": round(result.latency_ms, 1),
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "cost_usd": round(result.cost_usd, 8),
                    "insight_text": result.insight_text,
                }
            )


def summarize(rows: list[tuple[BenchmarkCase, EvalResult]]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}

    scored = [r for _, r in rows if r.hallucination_flag is not None]
    return {
        "n": n,
        "grounded_rate": sum(r.grounded for _, r in rows) / n,
        "hallucination_rate": (sum(r.hallucination_flag for r in scored) / len(scored)) if scored else None,
        "judge_scored_count": len(scored),
        "avg_latency_ms": sum(r.latency_ms for _, r in rows) / n,
        "avg_cost_usd": sum(r.cost_usd for _, r in rows) / n,
        "total_cost_usd": sum(r.cost_usd for _, r in rows),
    }


def print_summary(summary: dict) -> None:
    if summary.get("n", 0) == 0:
        print("no results")
        return
    print(f"\n=== summary ({summary['n']} cases) ===")
    print(f"grounded_rate:      {summary['grounded_rate']:.1%}")
    if summary["hallucination_rate"] is not None:
        print(
            f"hallucination_rate: {summary['hallucination_rate']:.1%} "
            f"({summary['judge_scored_count']}/{summary['n']} scored by judge)"
        )
    else:
        print("hallucination_rate: unscored (all judge calls failed)")
    print(f"avg_latency_ms:     {summary['avg_latency_ms']:.1f}")
    print(f"avg_cost_usd:       {summary['avg_cost_usd']:.6f}")
    print(f"total_cost_usd:     {summary['total_cost_usd']:.6f}")


def _repo_root() -> Path:
    # .../services/insight_service/src/insight_service/eval/run_benchmark.py -> repo root
    return Path(__file__).resolve().parents[5]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--cases", default=None, help="defaults to <repo root>/benchmarks/cases.yaml")
    parser.add_argument("--out-dir", default=None, help="defaults to <repo root>/benchmarks/results")
    args = parser.parse_args()

    cases_path = Path(args.cases) if args.cases else _repo_root() / "benchmarks" / "cases.yaml"
    out_dir = Path(args.out_dir) if args.out_dir else _repo_root() / "benchmarks" / "results"

    cases = load_cases(cases_path)
    print(f"loaded {len(cases)} cases from {cases_path}")
    print(f"running prompt_version={args.prompt_version} model={args.model}\n")

    rows = asyncio.run(run_benchmark(cases, args.prompt_version, args.model))

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{timestamp}_{args.prompt_version}_{args.model}.csv"
    write_csv(rows, out_path)
    print(f"\nwrote {len(rows)} rows to {out_path}")

    print_summary(summarize(rows))


if __name__ == "__main__":
    main()
