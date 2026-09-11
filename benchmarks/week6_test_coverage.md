# Week 6 / Layer 3 — api service unit test coverage

`services/api/.venv/bin/pytest services/api/tests -q --cov=api --cov-report=term-missing`

33 tests, all passing, 93% statement coverage on `services/api/src/api`.

```
Name                                         Stmts   Miss  Cover   Missing
--------------------------------------------------------------------------
services/api/src/api/__init__.py                 0      0   100%
services/api/src/api/audit.py                    9      0   100%
services/api/src/api/auth.py                    58      4    93%   86, 88-89, 105
services/api/src/api/db/__init__.py              0      0   100%
services/api/src/api/db/base.py                 11      2    82%   17-18
services/api/src/api/db/models.py               60      0   100%
services/api/src/api/deps.py                    39      0   100%
services/api/src/api/main.py                    18      1    94%   33
services/api/src/api/rate_limit.py              12      0   100%
services/api/src/api/rbac.py                    10      0   100%
services/api/src/api/routers/__init__.py         0      0   100%
services/api/src/api/routers/audit_logs.py      29      4    86%   42, 44, 46, 48
services/api/src/api/routers/auth.py            88      3    97%   93, 151, 173
services/api/src/api/routers/coach.py           29      1    97%   45
services/api/src/api/routers/config.py          30     10    67%   32-48, 58-74
services/api/src/api/routers/devices.py         37      0   100%
services/api/src/api/routers/features.py        21      0   100%
services/api/src/api/routers/insights.py        31     12    61%   34-72
services/api/src/api/routers/users.py           24      1    96%   33
services/api/src/api/settings.py                14      0   100%
--------------------------------------------------------------------------
TOTAL                                          520     38    93%
```

The two weakest files — `routers/config.py` (67%) and `routers/insights.py`
(61%) — are the two routers that proxy to another live HTTP service
(`config_service`, `insight_service`); the untested lines are their
success-path `httpx` calls, which would need a mocked transport to exercise
without those services actually running. Everything RBAC/audit-related
(`deps.py`, `audit.py`, `rbac.py`, the `users`/`features`/`devices`/`coach`
routers) is at 96-100% — that's the part this week's KPI is actually about.

`tests/test_route_auth.py` is a structural test (walks `app.routes`), not
reflected as extra statement coverage but is the thing that catches a future
endpoint forgetting an auth dependency, which line coverage alone wouldn't.
