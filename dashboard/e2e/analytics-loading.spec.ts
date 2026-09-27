import { expect, test, type Page } from "@playwright/test";

function report(id: number) {
  return { id, report: { date: "2026-09-25" }, prediction: { sif_score: 0.6 } };
}

async function stubAnalytics(page: Page) {
  await page.route("**/api/**", (route) => route.abort());
  await page.route("**/api/metrics/summary", (route) => route.fulfill({
    json: { n_reports: 4554, n_flagged: 4554, flag_rate: 1, flag_threshold: 0.5 },
  }));
  await page.route("**/api/density?*", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/patterns?*", (route) => route.fulfill({ json: [] }));
}

test("slow later analytics page and transient failure still load the full report walk", async ({ page }) => {
  test.setTimeout(30_000);
  await stubAnalytics(page);
  const offsets: number[] = [];
  await page.route("**/api/reports?*", async (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    offsets.push(offset);
    if (offset === 1000 && offsets.filter((value) => value === 1000).length === 1) {
      await route.fulfill({ status: 503, body: "Temporarily unavailable" });
      return;
    }
    if (offset === 2000) await new Promise((resolve) => setTimeout(resolve, 4200));
    await route.fulfill({ json: Array.from({ length: Math.max(0, Math.min(1000, 4554 - offset)) }, (_, i) => report(offset + i + 1)) });
  });

  await page.goto("/#/analytics");
  await expect(page.getByText("4,554 reports analysed")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("register truncated for this view")).toHaveCount(0);
  expect(offsets).toEqual([0, 1000, 1000, 2000, 3000, 4000]);
});

test("exhausted later-page retry hides the incomplete report walk", async ({ page }) => {
  await stubAnalytics(page);
  let laterAttempts = 0;
  await page.route("**/api/reports?*", (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    if (offset === 1000) {
      laterAttempts++;
      return route.fulfill({ status: 503, body: "Temporarily unavailable" });
    }
    return route.fulfill({ json: Array.from({ length: 1000 }, (_, i) => report(offset + i + 1)) });
  });

  await page.goto("/#/analytics");
  await expect(page.getByText("Analytics data unavailable", { exact: false })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/reports analysed/)).toHaveCount(0);
  expect(laterAttempts).toBe(2);
});

test("10,000-report ceiling is labelled truncated, not complete", async ({ page }) => {
  test.setTimeout(30_000);
  await stubAnalytics(page);
  const offsets: number[] = [];
  await page.route("**/api/reports?*", (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    offsets.push(offset);
    return route.fulfill({ json: Array.from({ length: 1000 }, (_, i) => report(offset + i + 1)) });
  });

  await page.goto("/#/analytics");
  await expect(page.getByText("10,000 reports analysed", { exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/first 10,000 reports analysed — register truncated for this view/)).toBeVisible();
  expect(offsets).toContain(9000);
  expect(offsets).not.toContain(10000);
});

test("aggregate requests retain a short timeout", async ({ page }) => {
  await stubAnalytics(page);
  await page.route("**/api/reports?*", (route) => route.fulfill({ json: [] }));
  let finishRoute!: () => void;
  const routeFinished = new Promise<void>((resolve) => { finishRoute = resolve; });
  await page.route("**/api/density?*", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 4500));
    await route.fulfill({ json: [] }).catch(() => {});
    finishRoute();
  });

  await page.goto("/#/analytics");
  await expect(page.getByText("0 reports analysed")).toBeVisible();
  await page.getByRole("tab", { name: "Hotspots" }).click();
  await expect(page.getByText("Analytics data unavailable", { exact: false }).first()).toBeVisible({ timeout: 5000 });
  await routeFinished;
});
