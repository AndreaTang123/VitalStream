import { defineConfig } from "@playwright/test";

/**
 * week7 Step 10: three E2E paths, not a coverage suite — see
 * e2e/README.md-equivalent note in each spec file for why these three.
 * Requires the full stack up (docker compose, or the manual per-service
 * commands in the root README) and `scripts/seed.py` already run; these
 * are not run in CI without that stack, see README "本地启动".
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
});
