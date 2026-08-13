"""Simulated wearable device: replays a PPG-DaLiA subject's wrist BVP signal
against the ingestion HTTP API in fixed-size chunks (week1-2-layer1-guide.md
Step 3). HTTP POST only for now — WebSocket streaming is a later addition.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from vitalstream_common.schemas import SignalType

from device_simulator.ppg_dalia import BVP_SAMPLE_RATE_HZ, default_data_dir, load_wrist_bvp


async def replay(
    *,
    data_dir: Path,
    subject: str,
    device_id: UUID,
    ingestion_url: str,
    speed: float,
    chunk_seconds: float,
) -> None:
    bvp = load_wrist_bvp(data_dir, subject)
    chunk_size = int(BVP_SAMPLE_RATE_HZ * chunk_seconds)
    total_chunks = len(bvp) // chunk_size
    # Chunk timestamps are derived from a fixed base + simulated elapsed time,
    # not wall-clock send time, so window boundaries stay exact regardless of
    # network/event-loop jitter (the pacing sleep below only controls *when*
    # each chunk is sent, not what timestamp it claims).
    base_ts = time.time()

    async with httpx.AsyncClient(base_url=ingestion_url, timeout=10.0) as client:
        for i in range(total_chunks):
            chunk = bvp[i * chunk_size : (i + 1) * chunk_size]
            payload = {
                "signal_type": SignalType.PPG.value,
                "sample_rate_hz": BVP_SAMPLE_RATE_HZ,
                "start_ts": base_ts + i * chunk_seconds,
                "values": chunk.tolist(),
            }
            response = await client.post(f"/api/v1/devices/{device_id}/signals", json=payload)
            response.raise_for_status()
            if i % 10 == 0:
                print(f"[{subject}] chunk {i}/{total_chunks} -> {response.json()}")
            await asyncio.sleep(chunk_seconds / speed)

    print(f"[{subject}] done: replayed {total_chunks} chunks ({total_chunks * chunk_seconds:.0f}s of signal)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="S2", help="PPG-DaLiA subject id, e.g. S2")
    parser.add_argument("--device-id", default=None, help="UUID to tag this device with (random if omitted)")
    parser.add_argument("--ingestion-url", default="http://localhost:8001")
    parser.add_argument("--speed", type=float, default=20.0, help="playback speed multiplier (1.0 = real-time)")
    parser.add_argument("--chunk-seconds", type=float, default=1.0)
    parser.add_argument("--data-dir", default=None, help="defaults to <repo root>/data/raw/ppg_dalia/PPG_FieldStudy")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else default_data_dir()
    device_id = UUID(args.device_id) if args.device_id else uuid4()
    print(f"replaying subject={args.subject} as device_id={device_id} at {args.speed}x from {data_dir}")

    asyncio.run(
        replay(
            data_dir=data_dir,
            subject=args.subject,
            device_id=device_id,
            ingestion_url=args.ingestion_url,
            speed=args.speed,
            chunk_seconds=args.chunk_seconds,
        )
    )


if __name__ == "__main__":
    main()
