"""Benchmark harness for hallucination rate / groundedness (PRD 3.2/6.2).

`BENCHMARK_CASES` is meant to be replaced by the "small hand-built benchmark
set" the PRD calls for — real cases with real feature inputs, reviewed by a
human for what a grounded, non-diagnostic insight should look like. The
scoring heuristics here (does the output reference the feature values it was
given, does it use disallowed diagnostic language) are deliberately simple
placeholders, not a real eval methodology.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

DIAGNOSTIC_TERMS = ("diagnos", "you have a condition", "disease", "prescri")


class BenchmarkCase(BaseModel):
    name: str
    features: dict[str, float]


@dataclass
class EvalResult:
    groundedness_score: float
    hallucinated: bool


@dataclass
class BenchmarkReport:
    case_count: int
    hallucination_rate: float
    avg_groundedness_score: float


def score_insight(features: dict[str, float], content: str) -> EvalResult:
    lowered = content.lower()
    referenced = sum(1 for key in features if key.replace("_", " ") in lowered)
    groundedness = referenced / len(features) if features else 0.0
    hallucinated = any(term in lowered for term in DIAGNOSTIC_TERMS)
    return EvalResult(groundedness_score=groundedness, hallucinated=hallucinated)


def summarize(results: list[EvalResult]) -> BenchmarkReport:
    if not results:
        return BenchmarkReport(case_count=0, hallucination_rate=0.0, avg_groundedness_score=0.0)

    hallucination_rate = sum(r.hallucinated for r in results) / len(results)
    avg_groundedness = sum(r.groundedness_score for r in results) / len(results)
    return BenchmarkReport(
        case_count=len(results),
        hallucination_rate=hallucination_rate,
        avg_groundedness_score=avg_groundedness,
    )


BENCHMARK_CASES: list[BenchmarkCase] = [
    BenchmarkCase(name="low_resting_hr", features={"resting_heart_rate": 52.0}),
    BenchmarkCase(name="poor_sleep_quality", features={"sleep_quality_score": 0.3}),
]
