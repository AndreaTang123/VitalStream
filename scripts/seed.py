"""Seed demo accounts + devices for local dev/demo (week6 Step 10).

Creates patient A / patient B / coach C / admin O, binds the PPG-DaLiA
subjects Week 1-5 already replay (S2, S3) to A and B as devices with
deterministic UUIDs (so `--device-id` on the simulator lines up with a real
`devices` row instead of a random one ingestion would reject), and grants
coach C access to patient A only — B stays unauthorized for C, which is what
the RBAC demo (README "Deep Dives → RBAC & audit log design") exercises.

Run with the api service's venv so `api`/`vitalstream_common` are importable:

    services/api/.venv/bin/python -m scripts.seed

Idempotent: re-running skips anything that already exists by email/device id.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from api.auth import hash_password
from api.db.base import AsyncSessionLocal
from api.db.models import CoachPatientORM, DeviceORM, UserORM
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from vitalstream_common.schemas import DeviceStatus, Role

LOADTEST_EMAIL = "loadtest@vitalstream.dev"
_LOADTEST_DEVICE_NAMESPACE = uuid.UUID("b8b3f2b0-6b1a-4b2e-9c1a-2f6a8b0c4d3e")


def loadtest_device_uuid(index: int) -> uuid.UUID:
    """Deterministic (uuid5, not uuid4) so re-running --load-devices is
    idempotent — same ids every time, so the ON CONFLICT DO NOTHING bulk
    insert actually dedupes instead of piling up new rows each run."""
    return uuid.uuid5(_LOADTEST_DEVICE_NAMESPACE, f"loadtest-device-{index}")

DEMO_PASSWORD = "password123"

# Deterministic so re-running the script, or pointing the simulator at these
# ids explicitly (`--device-id`), always resolves to the same devices row.
_DEVICE_NAMESPACE = uuid.UUID("6f6a7c3e-2f3a-4c1a-9c0a-9e0b6a2b8f11")


def device_uuid(subject: str) -> uuid.UUID:
    return uuid.uuid5(_DEVICE_NAMESPACE, f"vitalstream-device-{subject}")


USERS = [
    ("patient-a@vitalstream.dev", Role.PATIENT, "Patient A"),
    ("patient-b@vitalstream.dev", Role.PATIENT, "Patient B"),
    ("coach-c@vitalstream.dev", Role.COACH, "Coach C"),
    ("admin-o@vitalstream.dev", Role.ADMIN, "Admin O"),
]

# (owner email, PPG-DaLiA subject id)
DEVICES = [
    ("patient-a@vitalstream.dev", "S2"),
    ("patient-b@vitalstream.dev", "S3"),
]

COACH_GRANTS = [
    # coach, patient
    ("coach-c@vitalstream.dev", "patient-a@vitalstream.dev"),
]


async def _get_or_create_user(session, email: str, role: Role, display_name: str) -> UserORM:
    result = await session.execute(select(UserORM).where(UserORM.email == email))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = UserORM(
        email=email,
        hashed_password=hash_password(DEMO_PASSWORD),
        role=role,
        display_name=display_name,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()
    print(f"created user {email} ({role.value})")
    return user


async def _get_or_create_device(session, device_id: uuid.UUID, owner: UserORM, subject: str) -> None:
    result = await session.execute(select(DeviceORM).where(DeviceORM.id == device_id))
    if result.scalar_one_or_none() is not None:
        return

    session.add(
        DeviceORM(
            id=device_id,
            user_id=owner.id,
            device_type="simulated-ppg",
            status=DeviceStatus.ACTIVE,
            bound_at=datetime.now(UTC),
        )
    )
    print(f"bound device {device_id} (subject={subject}) to {owner.email}")


async def _grant_coach_access(session, coach: UserORM, patient: UserORM, granted_by: UserORM) -> None:
    result = await session.execute(
        select(CoachPatientORM).where(
            CoachPatientORM.coach_id == coach.id, CoachPatientORM.patient_id == patient.id
        )
    )
    if result.scalar_one_or_none() is not None:
        return

    session.add(
        CoachPatientORM(
            coach_id=coach.id,
            patient_id=patient.id,
            granted_at=datetime.now(UTC),
            granted_by=granted_by.id,
        )
    )
    print(f"granted {coach.email} access to {patient.email}")


async def _bulk_register_load_devices(session, owner: UserORM, count: int) -> list[uuid.UUID]:
    """week8 Step 3: ingestion rejects any device_id that isn't a `devices`
    row (week6), so a load test needs its devices registered first. Bulk
    `INSERT ... ON CONFLICT DO NOTHING` rather than one-row-at-a-time ORM
    inserts — at a few thousand devices, per-row round trips would make
    *seeding* the slow part of the load test setup."""
    now = datetime.now(UTC)
    device_ids = [loadtest_device_uuid(i) for i in range(count)]
    rows = [
        {
            "id": device_id,
            "user_id": owner.id,
            "device_type": "loadtest",
            "status": DeviceStatus.ACTIVE,
            "bound_at": now,
        }
        for device_id in device_ids
    ]
    # Batch the insert (a single 5000-row VALUES list is a lot of SQL text)
    # rather than one INSERT per device.
    batch_size = 1000
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        stmt = pg_insert(DeviceORM).values(batch).on_conflict_do_nothing(index_elements=["id"])
        await session.execute(stmt)
    return device_ids


async def seed(load_devices: int = 0) -> None:
    async with AsyncSessionLocal() as session:
        users = {
            email: await _get_or_create_user(session, email, role, name)
            for email, role, name in USERS
        }
        admin = users["admin-o@vitalstream.dev"]

        for owner_email, subject in DEVICES:
            await _get_or_create_device(session, device_uuid(subject), users[owner_email], subject)

        for coach_email, patient_email in COACH_GRANTS:
            await _grant_coach_access(session, users[coach_email], users[patient_email], admin)

        await session.commit()

        load_device_ids: list[uuid.UUID] = []
        if load_devices > 0:
            loadtest_user = await _get_or_create_user(
                session, LOADTEST_EMAIL, Role.PATIENT, "Load Test Fleet"
            )
            await session.commit()
            load_device_ids = await _bulk_register_load_devices(session, loadtest_user, load_devices)
            await session.commit()

    print("\nDemo devices (pass to the simulator with --device-id):")
    for owner_email, subject in DEVICES:
        print(f"  {subject}: --device-id {device_uuid(subject)}  (owner: {owner_email})")
    print(f"\nAll seeded users share the password: {DEMO_PASSWORD}")

    if load_device_ids:
        out_path = Path(__file__).resolve().parent.parent / "loadtest" / "data" / "devices.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps([str(d) for d in load_device_ids]))
        print(f"\nRegistered {len(load_device_ids)} load-test devices -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--load-devices",
        type=int,
        default=0,
        help="also bulk-register this many devices (bound to a dedicated loadtest@ user) for k6",
    )
    args = parser.parse_args()
    asyncio.run(seed(load_devices=args.load_devices))
