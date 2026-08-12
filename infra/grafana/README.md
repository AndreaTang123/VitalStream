# Grafana

No dashboards yet. Once the services export Prometheus metrics (see
`infra/prometheus/prometheus.yml`), add provisioned dashboards here:

```
infra/grafana/
  dashboards/
    ingestion-throughput.json
    api-latency.json
  provisioning/
    datasources.yml
    dashboards.yml
```

and mount `infra/grafana/provisioning` into the `grafana` service in
`docker-compose.yml` so dashboards load automatically on startup, per PRD 5.4
and the week-8 milestone in `docs/PRD.md`.
