// week8 Step 4: k6 open-model load test against ingestion.
//
// `constant-arrival-rate` is the whole reason this is k6 and not Locust
// (which defaults to a closed model: it waits for a response before
// issuing the next request, so a slowing system silently lowers its own
// offered load and *understates* latency — "coordinated omission"). Here,
// DEVICES req/s are issued regardless of how fast ingestion answers, which
// is what "N devices each reporting once a second" actually means.
//
// Device ids and PPG payloads are both real, not random — see
// scripts/seed.py --load-devices (registers devices ingestion will accept)
// and prepare_payloads.py (slices actual PPG-DaLiA samples). Run:
//
//   DEVICES=100 DURATION=3m k6 run loadtest/ingest.js
//
import http from "k6/http";
import { check } from "k6";
import { SharedArray } from "k6/data";
import exec from "k6/execution";

const chunks = new SharedArray("ppg", () => JSON.parse(open("./data/ppg_chunks.json")));
const deviceIds = new SharedArray("devices", () => JSON.parse(open("./data/devices.json")));

const DEVICES = parseInt(__ENV.DEVICES || "50");
const BASE = __ENV.BASE_URL || "http://localhost:8001";
const TOKEN = __ENV.SERVICE_TOKEN;

if (DEVICES > deviceIds.length) {
  throw new Error(
    `DEVICES=${DEVICES} but only ${deviceIds.length} devices registered — ` +
      `run: services/api/.venv/bin/python -m scripts.seed --load-devices ${DEVICES}`,
  );
}

export const options = {
  scenarios: {
    devices: {
      executor: "constant-arrival-rate", // open model: N devices = N req/s, full stop
      rate: DEVICES,
      timeUnit: "1s",
      duration: __ENV.DURATION || "3m",
      preAllocatedVUs: Math.max(50, DEVICES),
      maxVUs: Math.max(200, DEVICES * 4),
    },
  },
  thresholds: {
    // The SLO, defined here before any run — see benchmarks/RESULTS.md for
    // what "stable" means and why lag (not just this threshold) is the
    // real arbiter.
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(99)<200"],
  },
  summaryTrendStats: ["avg", "p(50)", "p(95)", "p(99)", "max"],
};

export default function () {
  const i = exec.scenario.iterationInTest;
  const deviceId = deviceIds[i % DEVICES]; // round-robin, not random — each
  // device gets ~1 req/s, which is what lets feature_extraction's per-device
  // 8s window actually fill up during the test instead of every device
  // getting a random, uneven trickle of requests.
  const body = JSON.stringify({
    signal_type: "ppg",
    sample_rate_hz: 64,
    start_ts: Date.now() / 1000,
    values: chunks[i % chunks.length],
  });
  const res = http.post(`${BASE}/api/v1/devices/${deviceId}/signals`, body, {
    headers: { "Content-Type": "application/json", "X-Service-Token": TOKEN },
  });
  check(res, { "status is 202": (r) => r.status === 202 });
}
