import { expect, test, type Page } from "@playwright/test";

function report(id: number, text = `Queue test report ${id}`, site = "Test site") {
  return {
    id,
    report: {
      text,
      date: null,
      site,
      activity: "Inspection",
      contractor: null,
      source: "test",
    },
    prediction: { sif_score: id / 10000, band: "LOW", rule_probs: {}, gate_states: [] },
    created_at: "2026-09-27T10:00:00Z",
  };
}

async function stubQueueMetadata(page: Page, total: number) {
  await page.route("**/api/**", (route) => route.abort());
  await page.route("**/api/health", (route) => route.fulfill({ json: { status: "ok", n_reports: total } }));
  await page.route("**/api/rules", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/clusters?*", (route) => route.fulfill({ json: { clusters: [] } }));
}

test("queue hash links retain filters through refresh, history, and navigation", async ({ page }) => {
  await stubQueueMetadata(page, 2);
  await page.route("**/api/reports?*", (route) => route.fulfill({
    json: [report(1, "Crane hook inspection", "Dock"), report(2, "Pump seal inspection", "Plant")],
  }));

  await page.goto("/#/queue?q=crane");
  const grid = page.getByRole("grid", { name: "Safety reports" });
  await expect(grid.locator("#qrow-1")).toBeVisible();
  await expect(page.getByLabel("Search reports")).toHaveValue("crane");
  await page.reload();
  await expect(grid.locator("#qrow-1")).toBeVisible();
  await expect(page.getByLabel("Search reports")).toHaveValue("crane");
  await page.waitForTimeout(400);
  await expect(page).toHaveURL(/\/#\/queue\?q=crane$/);

  await page.getByLabel("Site").selectOption("Dock");
  await expect(page).toHaveURL(/\/#\/queue\?q=crane&site=Dock$/);
  await page.evaluate(() => { window.location.hash = "/queue?q=pump"; });
  await expect(page.getByLabel("Search reports")).toHaveValue("pump");
  await expect(page.getByLabel("Site")).toHaveValue("");
  await expect(grid.locator("#qrow-2")).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/#\/queue\?q=crane&site=Dock$/);
  await expect(page.getByLabel("Search reports")).toHaveValue("crane");
  await expect(page.getByLabel("Site")).toHaveValue("Dock");
  await page.goForward();
  await expect(page.getByLabel("Search reports")).toHaveValue("pump");
  await page.waitForTimeout(400);
  await expect(page).toHaveURL(/\/#\/queue\?q=pump$/);
  await page.goBack();
  await expect(grid.locator("#qrow-1")).toBeVisible();

  await grid.locator("#qrow-1").click();
  await expect(page).toHaveURL(/\/#\/report\/1$/);
  await page.waitForTimeout(400);
  await expect(page).toHaveURL(/\/#\/report\/1$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/#\/queue\?q=crane&site=Dock$/);
  await expect(page.getByLabel("Search reports")).toHaveValue("crane");
  await page.getByLabel("Search reports").press("End");
  await page.getByLabel("Search reports").pressSequentially(" hook");
  await expect(page.getByLabel("Search reports")).toHaveValue("crane hook");
  await expect(grid.locator("#qrow-1")).toBeVisible();
  await expect(page).toHaveURL(/\/#\/queue\?q=crane\+hook&site=Dock$/);
  await page.getByRole("link", { name: "Add report", exact: true }).click();
  await page.waitForTimeout(400);
  await expect(page).toHaveURL(/\/#\/ingest$/);
  await page.goBack();
  await expect(page.getByLabel("Search reports")).toHaveValue("crane hook");
  await expect(page.getByLabel("Site")).toHaveValue("Dock");
  await expect(page).toHaveURL(/\/#\/queue\?q=crane\+hook&site=Dock$/);
  await page.getByRole("button", { name: "Clear filters", exact: true }).click();
  await expect(page).toHaveURL(/\/#\/queue$/);
  await expect(grid.locator('[id^="qrow-"]')).toHaveCount(2);
  await page.getByLabel("Search reports").fill("crane");
  await page.getByRole("link", { name: "Add report", exact: true }).click();
  await page.waitForTimeout(400);
  await expect(page).toHaveURL(/\/#\/ingest$/);
});

test("slow queue page and transient error still produce the complete register", async ({ page }) => {
  test.setTimeout(30_000);
  await stubQueueMetadata(page, 4554);
  const offsets: number[] = [];
  await page.route("**/api/reports?*", async (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    offsets.push(offset);
    if (offset === 0) await new Promise((resolve) => setTimeout(resolve, 4200));
    if (offset === 1000 && offsets.filter((value) => value === 1000).length === 1) {
      await route.fulfill({ status: 503, body: "Temporarily unavailable" });
    } else {
      await route.fulfill({ json: Array.from({ length: Math.min(1000, 4554 - offset) }, (_, i) => report(offset + i + 1)) });
    }
  });

  await page.goto("/#/queue");
  await expect(page.getByRole("grid", { name: "Safety reports" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("4,554 reports", { exact: true })).toBeVisible();
  await page.getByLabel("Search reports").fill("Queue test report 4554");
  await expect(page.locator("#qrow-4554")).toBeVisible();
  expect(offsets).toEqual([0, 1000, 1000, 2000, 3000, 4000]);
});

test("failed page hides partial results and manual retry clears stale progress", async ({ page }) => {
  await stubQueueMetadata(page, 1001);
  let fail = true;
  let resumeRetry!: () => void;
  const retryReady = new Promise<void>((resolve) => { resumeRetry = resolve; });
  const offsets: number[] = [];
  await page.route("**/api/reports?*", async (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    offsets.push(offset);
    if (!fail && offset === 0) await retryReady;
    if (offset === 1000 && fail) {
      await route.fulfill({ status: 503, body: "Temporarily unavailable" });
    } else {
      await route.fulfill({ json: offset === 0 ? Array.from({ length: 1000 }, (_, i) => report(i + 1)) : [report(1001)] });
    }
  });

  await page.goto("/#/queue");
  await expect(page.getByRole("alert").filter({ hasText: "Could not load the report register" })).toBeVisible();
  await expect(page.getByRole("grid", { name: "Safety reports" })).toHaveCount(0);
  await expect(page.getByText("1,000 reports loaded; incomplete list hidden").first()).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Loading reports" })).toContainText("0 / 1,001");
  resumeRetry();
  await expect(page.getByRole("grid", { name: "Safety reports" })).toBeVisible();
  await expect(page.getByText("1,001 reports", { exact: true })).toBeVisible();
  expect(offsets).toEqual([0, 1000, 1000, 0, 1000]);
});

test("navigating away cancels a queued retry; Hindi error has a localized action", async ({ page }) => {
  await stubQueueMetadata(page, 1);
  let attempts = 0;
  await page.route("**/api/reports?*", (route) => {
    attempts++;
    return route.fulfill({ status: 503, body: "Temporarily unavailable" });
  });

  await page.goto("/#/queue");
  await expect.poll(() => attempts).toBe(1);
  await page.getByRole("link", { name: "Add report", exact: true }).click();
  await expect(page).toHaveURL(/#\/ingest/);
  await page.waitForTimeout(1200);
  expect(attempts).toBe(1);

  await page.getByRole("button", { name: "हिं", exact: true }).click();
  await page.goto("/#/queue");
  await expect(page.getByRole("alert").filter({ hasText: "रिपोर्ट रजिस्टर लोड नहीं हो सका" })).toBeVisible();
  await expect(page.getByRole("button", { name: "पुनः प्रयास करें", exact: true })).toBeVisible();
});
