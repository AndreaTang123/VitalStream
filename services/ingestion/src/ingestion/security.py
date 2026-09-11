"""Service-to-service auth for the ingest endpoint (PRD 4.5, week6 Step 7).

`POST /devices/{id}/signals` is called by the simulator/real device
firmware, not a browser with a user JWT — a device has no login session, so
the whole OAuth2/RBAC machinery in `api` doesn't apply here. A static shared
secret compared in constant time is enough to keep the endpoint from being
open to the internet, without adding auth-service latency to the hottest
path in the system.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from ingestion.config import settings


async def verify_service_token(x_service_token: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_service_token, settings.service_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid service token")
