import { expect, test } from "@playwright/test";
import { login } from "./helpers";

// Week 7 acceptance item #2: coach C sees authorized patient A, and is
// cleanly denied when reaching for unauthorized patient B via a hand-edited
// URL — resource-level RBAC (Week 6) surfacing correctly in the UI, not
// just at the API layer.
test("coach sees authorized patients and is denied on unauthorized ones", async ({ page }) => {
  // Patient B's id isn't something coach C can look up (that's the point of
  // this test) — fetch it as admin first, via the same BFF proxy the UI
  // uses, then log out and continue as the coach.
  await login(page, "admin-o@vitalstream.dev");
  const patients = await page.request.get("/api/proxy/coach/patients").then((r) => r.json());
  const patientB = patients.find((p: { email: string }) => p.email === "patient-b@vitalstream.dev");
  expect(patientB, "scripts/seed.py should have created patient-b@vitalstream.dev").toBeTruthy();
  await page.request.post("/api/auth/logout");

  await login(page, "coach-c@vitalstream.dev");
  await expect(page).toHaveURL("/patients");
  await expect(page.getByText("patient-a@vitalstream.dev")).toBeVisible();
  await expect(page.getByText("patient-b@vitalstream.dev")).not.toBeVisible();

  await page.getByRole("link", { name: "View →" }).first().click();
  await expect(page.getByText("最新健康洞察")).toBeVisible();

  await page.goto(`/patients/${patientB.id}`);
  await expect(page.getByText("Access denied")).toBeVisible();
});
