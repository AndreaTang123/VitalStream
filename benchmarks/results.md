# Ingestion throughput: before vs after (Week 3 Step 1 / Step 6)

## Headline result

Same machine, same concurrency (10), same duration (15s), same `benchmarks/load_test.py`:

| | RPS | P50 | P95 | P99 |
|---|---|---|---|---|
| **Before** (`send_and_wait`, asyncio loop, unwired batch config) | 384.9 | 25.77 ms | 28.47 ms | 29.79 ms |
| **After** (fire-and-forget `send()`, uvloop, wired `max_batch_size`) | 1841.8 | 3.96 ms | 14.82 ms | 27.39 ms |

**~4.8x throughput, ~6.5x P50 latency.** The single biggest lever was not uvloop —
it was `kafka_producer.py` using `AIOKafkaProducer.send_and_wait()`, which
blocks the HTTP response until Kafka acks the write. That directly
contradicts PRD 3.1's own design ("写入成功立刻返回 202，不要等下游处理完再返回").
Switched to `producer.send()` (hands the message to aiokafka's internal
accumulator and returns immediately; delivery failures are still logged via
`future.add_done_callback`, just asynchronously instead of blocking the caller).

## What didn't make it into the headline number, and why

Benchmarking this honestly took a few wrong turns worth recording, since each
one would have produced a misleading number if left unexamined:

1. **uvloop alone showed no benefit, or a slight regression** (asyncio ~770
   RPS vs uvloop ~615 RPS at concurrency=20, reproduced twice each). Isolating
   the raw Kafka produce call (no HTTP at all) showed the same ~800 RPS
   ceiling regardless of event loop — the bottleneck wasn't event-loop
   dispatch at all.
2. **That ceiling turned out to be `linger_ms=20` interacting with test
   concurrency**, not a real system limit: raising concurrency from 20 to 100
   on the raw-Kafka microbenchmark jumped throughput from ~855 to ~23,225 RPS
   (27x). At low concurrency, every request effectively waits out a fixed
   ~20-25ms batching/ack window, so throughput ≈ concurrency / that fixed
   latency — a straight line that has nothing to do with uvloop.
3. **The load-test client itself was then the bottleneck at concurrency=100**:
   `httpx.AsyncClient`'s default `max_keepalive_connections=20` meant most of
   100 concurrent workers were paying a fresh TCP handshake per request.
   Fixed by sizing `httpx.Limits` to the requested concurrency
   (`benchmarks/load_test.py`).
4. **With that fixed, concurrency=100 against the full HTTP+Kafka endpoint
   collapsed into queueing** (P50 250ms, P99 ~3s) — a single uvicorn worker
   process saturating, a different bottleneck than any of the above. Swept
   concurrency 10/30/50/100 and found the system stays in a clean,
   non-queueing regime only around concurrency ≤ 10-15 with this
   single-process setup. That's why the headline comparison above uses
   concurrency=10: it's the highest level where the numbers reflect the code
   change being tested rather than an unrelated queueing collapse.
   Multi-worker/multi-process scaling is real future work — appropriately
   Week 8's full load-testing pass, not this week's.

So the honest takeaway isn't "uvloop made it faster" — on this dev machine,
in this workload, it didn't move the needle on its own. The real win was
fixing a request path that was accidentally synchronous end-to-end. uvloop
and the batch-size fix are both in place and don't hurt, but neither should
be the headline claim.

## Reproducing

```bash
# terminal 1: start ingestion (uvloop, fixed producer)
services/ingestion/.venv/bin/python -m ingestion.run

# terminal 2
services/ingestion/.venv/bin/python benchmarks/load_test.py --concurrency 10 --duration 15
```
