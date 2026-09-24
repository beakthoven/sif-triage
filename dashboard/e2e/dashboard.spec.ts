import { expect, test } from "@playwright/test";

test.describe.serial("HSE dashboard", () => {
  test("supports the complete live review workflow", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });

    await page.goto("/");
    await expect(page.getByRole("tab", { name: /^Triage/ })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Insights" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Decisions" })).toBeVisible();

    await page.getByRole("button", { name: /^All reports/ }).click();
    await page.getByPlaceholder("Search reports").fill("quartz");
    await expect(page.getByText(/slab of quartz/i)).toBeVisible();
    await page.getByRole("button", { name: "Why this score?" }).click();
    await expect(page.getByRole("button", { name: "Why this score?" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    await page.getByPlaceholder("Search reports").fill("");
    await page.getByRole("button", { name: /^Needs decision/ }).click();
    await expect(page.getByText("Manual review required").first()).toBeVisible();

    const uniqueReport = `UX verification drill ${Date.now()}: simulated evacuation only, no incident occurred.`;
    await page.getByLabel("Classify a report").fill(uniqueReport);
    await page.getByRole("button", { name: "Classify" }).click();
    await expect(page.getByText("Manual review required").first()).toBeVisible();
    await page.getByRole("button", { name: "Not SIF-potential" }).click();

    await page.getByRole("tab", { name: /Decisions/ }).click();
    await expect(page.getByRole("cell", { name: "Not SIF-potential" }).first()).toBeVisible();
    await expect(page.getByRole("cell", { name: "HSE reviewer" }).first()).toBeVisible();

    await page.getByRole("tab", { name: "Insights" }).click();
    await expect(page.getByRole("tab", { name: "Locations" })).toBeVisible();
    await expect(page.getByText("Show all locations").first()).toBeVisible();
    await page.getByRole("tab", { name: "Recurring patterns" }).click();
    await expect(page.getByRole("tab", { name: "Site × activity" })).toBeVisible();
    await page.getByRole("tab", { name: "Activity × failed barrier" }).click();
    await expect(page.getByText("Statistical detail").first()).toBeVisible();

    await page.getByRole("button", { name: "हिं" }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "hi");
    await expect(page.getByRole("tab", { name: /ट्रायाज/ })).toBeVisible();
    await page.getByRole("button", { name: "EN" }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");

    expect(consoleErrors).toEqual([]);
  });

  test("keeps the mobile layout within the viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const widths = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(widths.content).toBe(widths.viewport);
    await expect(page.getByRole("heading", { name: "Review the reports that need attention" })).toBeVisible();
  });

  test("preserves unfinished triage work across workspace changes", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Classify a report").fill("Unsubmitted field observation");
    await page.getByRole("tab", { name: "Insights" }).click();
    await page.getByRole("tab", { name: /^Triage/ }).click();
    await expect(page.getByLabel("Classify a report")).toHaveValue("Unsubmitted field observation");
  });

  test("imports the real demo batch and re-ranks locations", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("tab", { name: "Insights" }).click();
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Import CSV" }).click();
    await (await chooser).setFiles({
      name: "one-report.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "text,date,site,activity\nRoutine housekeeping observation with no hazard,2026-09-10,UX Test Site,inspection\n",
      ),
    });
    await expect(page.getByText("accepted 1/1")).toBeVisible();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Run demo batch" }).click();
    await expect(page.getByText("accepted 500/500")).toBeVisible({ timeout: 90_000 });
    await expect(page.getByText(/just climbed to #1/)).toBeVisible();
  });

  test("falls back honestly when the API is unavailable", async ({ page }) => {
    await page.route("**/api/**", (route) => route.abort());
    await page.goto("/");
    await expect(page.getByText("Offline demo", { exact: true })).toBeVisible();
    await page.getByLabel("Classify a report").fill("Short offline test report");
    await page.getByRole("button", { name: "Classify" }).click();
    await expect(page.getByText("Manual review required")).toBeVisible();
    await expect(page.getByText(/offline placeholder/i)).toBeVisible();
  });
});
