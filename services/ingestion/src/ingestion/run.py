"""Run the ingestion service with uvloop as the asyncio event loop policy.

`uvicorn ingestion.main:app --loop uvloop` achieves the same thing; this module
exists so the loop-policy choice is explicit and testable rather than buried in
a CLI flag (PRD 3.1 / 4.2: uvloop tuning is a deliberate perf-tuning highlight).
"""

import uvicorn
import uvloop


def main() -> None:
    uvloop.install()
    uvicorn.run("ingestion.main:app", host="0.0.0.0", port=8001, loop="uvloop")


if __name__ == "__main__":
    main()
