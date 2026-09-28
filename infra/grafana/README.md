# Grafana

Provisioned, not hand-clicked — `docker-compose.yml` mounts
`infra/grafana/provisioning` (read-only) into the container, so a fresh
`docker compose up` shows the real dashboard with no manual setup:

```
infra/grafana/provisioning/
  datasources/datasources.yml   # Prometheus + Jaeger
  dashboards/dashboards.yml     # points Grafana at ./files
  dashboards/files/
    vitalstream.json            # the one dashboard: Ingestion / Pipeline / AI / Platform rows
```

If you tweak a panel in the UI, **Export → JSON** back into
`dashboards/files/vitalstream.json` rather than leaving the change only in
the running container's state (`GF_AUTH_ANONYMOUS_ENABLED=true` makes the
dashboard viewable without logging in, but editing still requires the
`admin`/`admin` login from `docker-compose.yml`).

See the top-level README's "Observability" section for what each row shows
and why (pipeline E2E latency definition, cache hit rate, the gray-release
rollout made visible as two lines whose ratio matches `rollout_pct`).
