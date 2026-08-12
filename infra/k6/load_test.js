// k6 load test for the ingestion service (PRD 5.1/6.1/7 week-8 milestone).
// Run: k6 run infra/k6/load_test.js
// Override target/concurrency: k6 run -e BASE_URL=http://localhost:8001 -e VUS=200 infra/k6/load_test.js
import http from "k6/http";
import { check } from "k6";
import { uuidv4 } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8001";

export const options = {
  scenarios: {
    concurrent_devices: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 50),
      duration: __ENV.DURATION || "60s",
    },
  },
};

export default function () {
  const deviceId = uuidv4();
  const payload = JSON.stringify([
    {
      signal_type: "heart_rate",
      value: 60 + Math.random() * 40,
      timestamp: new Date().toISOString(),
    },
  ]);

  const response = http.post(`${BASE_URL}/api/v1/devices/${deviceId}/signals`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(response, { "status is 200": (r) => r.status === 200 });
}
