#!/usr/bin/env bash
# week8 Step 5: run a fixed set of device-count tiers, each independently,
# rather than one long ramp — makes "is this tier stable" a yes/no question
# instead of eyeballing a slope.
#
# Usage: DEVICE_TIERS="25 50 100 250 500 1000" RUNS_PER_TIER=1 ./run_steps.sh
set -euo pipefail
cd "$(dirname "$0")"

SERVICE_TOKEN="${SERVICE_TOKEN:?set SERVICE_TOKEN (see .env)}"
BASE_URL="${BASE_URL:-http://localhost:8001}"
DURATION="${DURATION:-90s}"
RUNS_PER_TIER="${RUNS_PER_TIER:-1}"
DEVICE_TIERS="${DEVICE_TIERS:-25 50 100 250 500 1000}"

mkdir -p ../benchmarks/raw

for n in $DEVICE_TIERS; do
  for run in $(seq 1 "$RUNS_PER_TIER"); do
    echo "=== DEVICES=$n run=$run/$RUNS_PER_TIER ==="
    DEVICES="$n" DURATION="$DURATION" BASE_URL="$BASE_URL" SERVICE_TOKEN="$SERVICE_TOKEN" \
      k6 run --summary-export="../benchmarks/raw/ingest_${n}_run${run}.json" ingest.js || true
    echo "--- draining backlog (60s) before next run ---"
    sleep 60
  done
done

echo "done — raw summaries in benchmarks/raw/"
