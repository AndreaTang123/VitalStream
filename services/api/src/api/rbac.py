"""Role-based access control (PRD 3.3, 5.3): per-endpoint role allowlists."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from vitalstream_common.schemas import Role

from api.auth import CurrentUser, get_current_user


def require_role(*allowed_roles: Role):
    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{current_user.role}' is not permitted to access this resource",
            )
        return current_user

    return _check
