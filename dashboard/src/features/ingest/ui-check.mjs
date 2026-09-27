import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";

const base = process.env.UI_CHECK_BASE ?? "http://127.0.0.1:8246";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ timezoneId: "Asia/Kolkata" });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
let importStarted = false;
let interrupted = false;
let failMeta = true;
let reviewWrites = 0;
const rows = [1, 2].map((id) => ({
  id, report_id: id, field: "sif_label", old_value: null,
  new_value: "sif_potential", labeler: "qa.reviewer", rationale: "Recorded evidence",
  source: "override", created_at: "2026-09-27T00:00:00Z",
}));
await context.route("**/api/**", async (route) => {
  const path = new URL(route.request().url()).pathname;
  const method = route.request().method();
  let body = {};
  let status = 200;
  if (path === "/api/health") {
    body = { status: "ok", api_version: "test", classifier: "test", model_version: "test", n_reports: importStarted ? 11 : 10, n_overrides: 2 };
  } else if (path === "/api/ingest" && method === "POST") {
    importStarted = true;
    if (interrupted) await new Promise((resolve) => setTimeout(resolve, 6_000));
    body = { received: 1, accepted: 1, rejected: 0, skipped_duplicates: 0, errors: [] };
  } else if (path === "/api/review") {
    if (method === "POST") reviewWrites += 1;
    body = rows;
  } else if (path === "/api/rules") {
    body = [];
  } else if (path === "/api/metrics/summary") {
    body = { n_reports: 10, n_flagged: 1, flag_rate: 0.1, mean_score: 0.2, n_overrides: 2, classifier: "test", model_version: "test", gate_trigger_counts: {} };
  } else if (path.startsWith("/api/reports/")) {
    const id = Number(path.split("/").at(-1));
    status = id === 1 && failMeta ? 503 : 200;
    body = {
      id, report: { text: `Report ${id} source evidence`, date: "2026-09-27", site: "QA site", activity: "inspection", contractor: null, source: "test" },
      prediction: { sif_score: 0.2, band: "LOW", rule_probs: {}, well_control: false, evidence_spans: [], gate_states: [], model_version: "test" },
      created_at: "2026-09-27T00:00:00Z",
    };
  }
  await route.fulfill({ status, json: body }).catch(() => {});
});

async function openCsv() {
  await page.goto(`${base}/#/ingest`);
  await page.reload();
  await page.waitForLoadState("networkidle");
  await page.getByRole("tab", { name: "Import CSV", exact: true }).click();
}
async function upload() {
  await page.locator('input[type="file"]').setInputFiles({
    name: "check.csv", mimeType: "text/csv", buffer: Buffer.from("text\nRoutine inspection report\n"),
  });
  await page.getByRole("dialog").getByRole("button", { name: "Start ingest", exact: true }).click();
}
try {
  await openCsv();
  await page.evaluate(() => { File.prototype.text = () => Promise.reject(new Error("Unreadable file")); });
  await page.locator('input[type="file"]').setInputFiles({ name: "broken.csv", mimeType: "text/csv", buffer: Buffer.from("text\nrow") });
  await expect(page.getByRole("alert")).toContainText("Could not read this file.");
  await expect(page.getByRole("button", { name: "Select CSV", exact: true })).toBeEnabled();
  console.log("PASS unreadable file clears busy state and shows recovery copy");

  await openCsv();
  await upload();
  await expect(page.getByTestId("kpi-accepted")).toContainText("1");
  await expect(page.getByText("No rejected rows.", { exact: true })).toBeVisible();
  console.log("PASS confirmed synchronous result retains authoritative counts");

  interrupted = true;
  importStarted = false;
  await openCsv();
  await upload();
  await expect(page.getByRole("button", { name: "Stop waiting", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Stop waiting", exact: true }).click();
  await expect(page.getByText("not confirmed", { exact: true })).toBeVisible({ timeout: 12_000 });
  await expect(page.getByTestId("kpi-net")).toContainText("+1");
  await expect(page.getByTestId("kpi-accepted")).toHaveCount(0);
  await expect(page.getByText("No rejected rows.", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/report count did not increase/)).toHaveCount(0);
  console.log("PASS increased global count does not claim batch completion or zero rejections");

  await page.goto(`${base}/#/decisions`);
  await page.waitForLoadState("networkidle");
  await expect(page.getByText("Report text unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("Report 2 source evidence", { exact: true })).toBeVisible();
  failMeta = false;
  const recovered = await page.evaluate(async () => {
    const { getReportMeta } = await import("/src/features/decisions/data.ts");
    return getReportMeta(1);
  });
  assert.equal(recovered?.id, 1);
  await page.getByRole("button", { name: "Correct", exact: true }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox").first().fill("qa.reviewer");
  await dialog.getByRole("combobox").first().selectOption("rules");
  await dialog.getByRole("textbox").last().fill("Missing control identified.");
  await dialog.getByRole("button", { name: "Record correction", exact: true }).click();
  await expect(dialog.getByText("A value is required.", { exact: true })).toBeVisible();
  assert.equal(reviewWrites, 0);
  console.log("PASS metadata errors settle, retry works, empty rule corrections cannot be saved");

  await page.clock.install({ time: new Date("2026-09-27T19:00:00Z") });
  const due = await page.evaluate(async () => (await import("/src/features/decisions/data.ts")).defaultDue("fir"));
  assert.equal(due, "2026-09-29");
  const copy = await page.evaluate(async () => {
    const { limitationItems } = await import("/src/features/limitations/limitations-panel.tsx");
    const { t } = await import("/src/features/analytics/phrases.ts");
    const { c } = await import("/src/features/report/copy.ts");
    return ["en", "hi"].map((lang) => ({
      limitations: limitationItems(lang),
      unavailable: t(lang, "noFabricatedData"),
      threshold: t(lang, "thresholdSummary", { threshold: 0.5 }),
      decision: c(lang, "decisionFailed"),
    }));
  });
  for (const locale of copy) {
    assert.equal(locale.limitations.length, 9);
    assert(locale.limitations.every((item) => item.title && (item.body.includes(".py") || item.body.includes(".json") || item.body.includes(".md"))));
    assert(locale.threshold.includes("0.5"));
    assert(locale.unavailable.length > 0 && locale.decision.length > 0);
  }
  console.log("PASS bilingual copy retains nine evidence-backed limitations and interpolation");
  assert.deepEqual(errors, []);
  console.log("PASS CAPA due date uses local calendar day; no browser runtime errors");
} catch (error) {
  console.error(await page.locator("body").innerText());
  console.error(errors);
  throw error;
} finally {
  await browser.close();
}
