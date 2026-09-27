import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) => route.abort());
});

test("missing report shows the localized not-found state, not an API error", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/reports/123456789", (route) => {
    requests++;
    return route.fulfill({ status: 404, body: "Not found" });
  });

  await page.goto("/#/report/123456789");
  await expect(page.getByText("Report not found", { exact: true })).toBeVisible();
  await expect(page.getByText("This report does not exist, or it has no stored prediction to explain.")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(requests).toBe(1);

  await page.getByRole("button", { name: "हिं", exact: true }).click();
  await expect(page.getByText("रिपोर्ट नहीं मिली", { exact: true })).toBeVisible();
  await expect(page.getByText("यह रिपोर्ट मौजूद नहीं है, या उसकी कोई संग्रहीत भविष्यवाणी नहीं है।")).toBeVisible();
});

test("server failure shows a retryable error, not report not found", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/reports/123456789", (route) => {
    requests++;
    return route.fulfill({ status: 500, body: "Internal server error" });
  });

  await page.goto("/#/report/123456789");
  await expect(page.getByRole("alert")).toContainText("Could not load this report");
  await expect(page.getByText("Report not found", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Try Again" }).click();
  await expect.poll(() => requests).toBeGreaterThan(2);
});

test("network failure shows an error, not report not found", async ({ page }) => {
  await page.goto("/#/report/123456789");
  await expect(page.getByRole("alert")).toContainText("Could not load this report");
  await expect(page.getByText("Report not found", { exact: true })).toHaveCount(0);
});

test("invalid report IDs show not found without requesting a report", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/reports/*", (route) => {
    requests++;
    return route.fulfill({ status: 500, body: "Should not request an invalid ID" });
  });

  for (const id of ["nonexistent", "0", "-1", "1.5", "1e2", "Infinity", "9007199254740992"]) {
    await page.goto(`/#/report/${id}`);
    await expect(page.getByText("Report not found", { exact: true })).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
  }
  expect(requests).toBe(0);
});
