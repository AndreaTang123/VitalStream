"""Run the ingestion service with uvloop as the asyncio event loop policy.

`uvicorn ingestion.main:app --loop uvloop` achieves the same thing; this module
exists so the loop-policy choice is explicit and testable rather than buried in
a CLI flag (PRD 3.1 / 4.2: uvloop tuning is a deliberate perf-tuning highlight).
"""

import uvicorn
import uvloop


def main() -> None:
    uvloop.install()
    # week8 Step 3: per-request access logging is real per-request overhead
    # on the hottest path in the system — fine at dev traffic, measurably
    # not fine once benchmarks/RESULTS.md's load test is pushing hundreds
    # of req/s through here. warning-level (not the uvicorn default info)
    # so a load test measures the endpoint, not the logger.
    uvicorn.run("ingestion.main:app", host="0.0.0.0", port=8001, loop="uvloop", log_level="warning")


if __name__ == "__main__":
    main()
