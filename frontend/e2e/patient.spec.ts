import { expect, test } from "@playwright/test";
import { login } from "./helpers";

// Week 7 acceptance item #1: patient A logs in and sees their own real
// insights/trend data — proof the whole pipeline (simulator -> ingestion ->
// Kafka -> feature_extraction -> insight_service -> api) reaches a browser.
// Requires scripts/seed.py to have run and the simulator to have produced at
// least one window for patient-a's device.
test("patient logs in and sees their own health data", async ({ page }) => {
  await login(page, "patient-a@vitalstream.dev");

  await expect(page).toHaveURL("/dashboard");
  await expect(page.getByText("最新健康洞察")).toBeVisible();
  await expect(page.getByText("特征趋势")).toBeVisible();
});

// Week 7 acceptance item #1, continued: clicking "生成洞察" produces a new
// insight without a manual page refresh.
test("generating an insight surfaces a new result without a manual refresh", async ({ page }) => {
  await login(page, "patient-a@vitalstream.dev");

  const generateButton = page.getByRole("button", { name: /生成洞察/ });
  await expect(generateButton).toBeVisible();
  await generateButton.click();

  await expect(page.getByText(/新洞察已生成|生成中/)).toBeVisible();
  await expect(page.getByText("新洞察已生成 ✓")).toBeVisible({ timeout: 60_000 });
});
