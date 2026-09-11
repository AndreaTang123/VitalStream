"""Meta-test (week6 Step 8/9): every non-public route must carry an auth
dependency somewhere in its dependency tree. This is deliberately a sweep
over `app.routes` rather than a per-endpoint assertion — permission checks
scattered across individual tests can miss a newly-added endpoint that
forgot `Depends(...)`; this test can't."""

from __future__ import annotations

from fastapi.routing import APIRoute

from api.main import app

# Endpoints that are intentionally public: health checks, OpenAPI docs, and
# the auth endpoints a not-yet-authenticated caller must be able to reach.
_PUBLIC_PATHS = {
    "/healthz",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
}

_AUTH_DEPENDENCY_QUALNAMES = {
    "get_current_user",
    "authorize_user_access",
    "authorize_device_access",
    "require_role.<locals>._check",
}


def _dependency_tree_has_auth(dependant) -> bool:
    for sub in dependant.dependencies:
        call = sub.call
        name = getattr(call, "__qualname__", getattr(call, "__name__", ""))
        if name in _AUTH_DEPENDENCY_QUALNAMES:
            return True
        if _dependency_tree_has_auth(sub):
            return True
    return False


def test_every_non_public_route_requires_auth():
    unguarded = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in _PUBLIC_PATHS:
            continue
        if not _dependency_tree_has_auth(route.dependant):
            unguarded.append(f"{sorted(route.methods)} {route.path}")

    assert unguarded == [], f"routes missing an auth dependency: {unguarded}"
