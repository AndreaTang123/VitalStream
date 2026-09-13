import { expect, test } from "@playwright/test";
import { login } from "./helpers";

// Week 7 acceptance item #3: an operator rolls back a config version, then
// finds that action — plus the coach.spec.ts denial that ran before it —
// in the audit log, with actor/action/target all legible. This is the
// "企业级交付" beat of the Week 8 demo recording.
test("operator rolls back a config version and sees it audited", async ({ page }) => {
  await login(page, "admin-o@vitalstream.dev");
  await page.goto("/admin/config");

  const rollbackButtons = page.getByRole("button", { name: "Rollback" });
  test.skip(
    (await rollbackButtons.count()) === 0,
    "no non-retired version to roll back — register/publish one first (README '认证与权限' curl flow)",
  );

  await rollbackButtons.first().click();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText(/Failed to/i)).not.toBeVisible();

  await page.goto("/admin/audit");
  await page.getByRole("combobox").selectOption("config.rollback");
  await expect(page.getByText("config.rollback").first()).toBeVisible();

  // The coach.spec.ts denial (run earlier in the suite) should also be
  // findable via the "denied only" filter.
  await page.getByRole("combobox").selectOption("");
  await page.getByRole("button", { name: /仅看被拒绝/ }).click();
  await expect(page.getByText("denied").first()).toBeVisible();
});
