"""Business-level Prometheus metric (week8 Step 1).

`authz_denied_total` is deliberately the *only* custom metric api exports —
everything else about a request (latency, status code, path) is already
covered by `prometheus-fastapi-instrumentator`'s generic
`http_request_duration_seconds` histogram (see main.py). This one exists
because "how often is RBAC actually rejecting something" isn't derivable
from HTTP status codes alone (a 403 could be a role-level check or a
resource-level one, and the generic histogram has no `action` label).

Label is `action` (a small, fixed set of endpoint categories: "role_check",
"user_access", "device_access") — never `actor_id`/`target_user_id`, which
would blow up cardinality with every new user (same reasoning as
`ingestion/metrics.py`'s docstring).
"""

from __future__ import annotations

from prometheus_client import Counter

AUTHZ_DENIED_TOTAL = Counter(
    "authz_denied_total", "RBAC denials (role-level or resource-level)", ["action"]
)
