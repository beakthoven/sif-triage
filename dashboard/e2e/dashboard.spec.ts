import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const API = process.env.E2E_API ?? "http://127.0.0.1:8232";
const uniqueTag = (prefix: string) => `${prefix}-${randomUUID().slice(0, 8)}`;
const csvCell = (value: string) => `"${value.replaceAll('"', '""')}"`;
const buildCsv = (tag: string, count: number, site: string, activity: string) => [
  "text,site,activity",
  ...Array.from({ length: count }, (_, i) =>
    [
      `${tag} row ${i + 1}: routine pump walkdown recorded a stable seal and no leak; work order ${i + 1} was closed.`,
      site,
      activity,
    ].map(csvCell).join(","),
  ),
].join("\n");

type SeededReport = { id: number; classifyBand: string | null };

async function seedReport(
  request: APIRequestContext,
  text: string,
  metadata: { site?: string; activity?: string } = {},
): Promise<SeededReport> {
  const response = await request.post(`${API}/api/classify?persist=1&llm=0`, {
    data: { text, source: "e2e", ...metadata },
    timeout: 30_000,
  });
  expect(response.ok(), `classify failed: ${response.status()} ${await response.text()}`).toBeTruthy();
  const body = (await response.json()) as { report_id?: number | null; band?: string | null };
  expect(body.report_id, "persist=1 returns the stored report id").toBeGreaterThan(0);
  return { id: body.report_id as number, classifyBand: body.band ?? null };
}

async function tabUntilFocused(page: Page, target: import("@playwright/test").Locator, maxTabs = 60) {
  for (let i = 0; i < maxTabs; i++) {
    if (await target.evaluate((element) => element === document.activeElement).catch(() => false)) return;
    await page.keyboard.press("Tab");
  }
  throw new Error("Keyboard focus did not reach the requested control");
}

const highBarrierReport = (tag: string) =>
  `During tank maintenance ${tag}, a worker entered the crude oil storage tank for cleaning without any gas test, and no standby attendant was posted at the manway. During lifting operations, a 12 tonne spool was suspended over workers and fell, striking a contractor below and causing a fractured leg.`;

test("isolated API is serving the real INT8 classifier", async ({ request }) => {
  const response = await request.get(`${API}/api/health`);
  expect(response.ok()).toBeTruthy();
  const health = (await response.json()) as { classifier: string; model_version: string; n_reports: number };
  expect(health.classifier).toBe("RealOnnxClassifier");
  expect(health.model_version).toContain("masked-v2");
  expect(health.n_reports).toBeGreaterThan(0);
});

test("queue renders reports; search and site filters narrow to real matches", async ({ page, request }) => {
  const tag = uniqueTag("queue-search");
  const text = `Unique searchable pump-seal observation ${tag}: no leak was present.`;
  const { id } = await seedReport(request, text, {
    site: "E2E Queue Site",
    activity: "pump inspection",
  });

  await page.goto(`${API}/#/queue`);
  const grid = page.getByRole("grid", { name: "Safety reports" });
  await expect(grid).toBeVisible({ timeout: 60_000 });
  const rows = grid.locator('[id^="qrow-"]');
  await expect(rows.first()).toBeVisible();

  const scores = grid.locator('[id^="qrow-"] [role="gridcell"][aria-colindex="6"]');
  const scoreCount = await scores.count();
  expect(scoreCount).toBeGreaterThan(2);
  const values: number[] = [];
  for (let i = 0; i < scoreCount; i++) {
    const match = (await scores.nth(i).innerText()).match(/\d+\.\d{2}/);
    expect(match, "rendered row contains its score").toBeTruthy();
    values.push(Number(match![0]));
  }
  for (let i = 1; i < values.length; i++) expect(values[i - 1]).toBeGreaterThanOrEqual(values[i]);

  await page.getByLabel("Search reports").fill(tag);
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText(tag);

  await page.getByLabel("Clear search").click();
  const siteFilter = page.getByLabel("Site");
  await expect(siteFilter.locator("option").filter({ hasText: "E2E Queue Site" })).toHaveCount(1);
  await siteFilter.selectOption({ label: "E2E Queue Site" });
  const rowForSeed = grid.locator(`#qrow-${id}`);
  await expect(rowForSeed).toContainText("E2E Queue Site");
  await expect(rowForSeed).toContainText("pump inspection");
});

test("queue compresses server-clustered reports and expands their individual rows", async ({ page, request }) => {
  const tag = uniqueTag("queue-cluster");
  const texts = [
    `During elevated maintenance ${tag}, a technician worked above the pump bay without a fall-protection harness. The worker slipped, caught the handrail, and no injury was reported. Version alpha.`,
    `During elevated maintenance ${tag}, a technician worked above the pump bay without a fall-protection harness. The worker slipped and caught the handrail; no injury was reported. Version beta.`,
    `During elevated maintenance ${tag}, a technician worked above the pump bay without a fall-protection harness. The worker slipped, caught the handrail and no injury was reported. Version gamma.`,
  ];
  const seeded = await Promise.all(texts.map((text) => seedReport(request, text)));
  await seedReport(request, `An unrelated warehouse inventory count found two sealed boxes and closed the shift log.`);
  const seededIds = seeded.map(({ id }) => id);

  const clustersResponse = await request.get(`${API}/api/clusters?min_cos=0.91`);
  expect(clustersResponse.ok(), `GET /api/clusters failed: ${clustersResponse.status()}`).toBeTruthy();
  const clusterBody = (await clustersResponse.json()) as {
    clusters: { member_ids: number[] }[];
  };
  const sharedCluster = clusterBody.clusters.find((cluster) =>
    seededIds.every((id) => cluster.member_ids.includes(id)),
  );
  expect(
    sharedCluster,
    `Backend integration drift: seeded reports ${seededIds.join(", ")} do not share a cluster at min_cos=0.91`,
  ).toBeTruthy();

  await page.goto(`${API}/#/queue`);
  const grid = page.getByRole("grid", { name: "Safety reports" });
  await expect(grid).toBeVisible({ timeout: 60_000 });
  await page.getByLabel("Search reports").fill(tag);

  const rows = grid.locator('[id^="qrow-"]');
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText(tag);
  const expander = grid.getByRole("button", { name: "2 similar reports" });
  await expect(expander).toHaveAttribute("aria-expanded", "false");
  await expander.click();
  await expect(grid.getByRole("button", { name: "Collapse similar reports" })).toHaveAttribute("aria-expanded", "true");
  for (const id of seededIds) await expect(grid.locator(`#qrow-${id}`)).toBeVisible();
  const nonRepresentativeIds = [...seededIds].sort((a, b) => a - b).slice(1);
  for (const id of nonRepresentativeIds) {
    await expect(grid.locator(`a[href="#/report/${id}"]`)).toBeVisible();
  }
  await expect(rows).toHaveCount(3);

  await grid.getByRole("button", { name: "Collapse similar reports" }).click();
  await expect(rows).toHaveCount(1);
  await expect(page.getByText("1 duplicate group · 2 reports collapsed", { exact: true })).toBeVisible();
});

test("report detail shows score, source evidence and fired barrier gates", async ({ page, request }) => {
  const tag = uniqueTag("report-detail");
  const seeded = await seedReport(request, highBarrierReport(tag), {
    site: "E2E Barrier Site",
    activity: "tank maintenance",
  });
  const storedResponse = await request.get(`${API}/api/reports/${seeded.id}`);
  expect(storedResponse.ok()).toBeTruthy();
  const stored = (await storedResponse.json()) as {
    prediction?: { band?: string | null } | null;
  };
  const storedBand = stored.prediction?.band ?? null;

  await page.goto(`${API}/#/report/${seeded.id}`);
  await expect(page.getByText("Report detail", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("triage score", { exact: true })).toBeVisible();
  await expect(page.getByText(/Review threshold/)).toBeVisible();
  if (storedBand === "HIGH") await expect(page.getByText("HIGH", { exact: true })).toBeVisible();
  await expect(page.getByText("Evidence", { exact: true })).toBeVisible();
  await expect(page.getByText(tag).first()).toBeVisible();
  const firedBarrierLabels = page.locator("[aria-label='Missing safeguard'], [aria-label='सुरक्षा उपाय अनुपस्थित']");
  await expect(firedBarrierLabels).toBeVisible();
  await expect(page.getByText(/No gas test was recorded before entry|No standby person was recorded/).first()).toBeVisible();

  if (storedBand === null) {
    test.info().annotations.push({
      type: "band assertion skipped",
      description: `GET /api/reports/${seeded.id} omitted prediction.band (classify response band: ${seeded.classifyBand ?? "absent"}).`,
    });
  }
});

test("decision form records a rationale that appears in the decisions register", async ({ page, request }) => {
  const tag = uniqueTag("decision-flow");
  const { id } = await seedReport(request, `Crane hook drifted near the walkway during maintenance ${tag}.`);
  const rationale = `Stop-work was called and the operator was re-briefed before resuming. ${tag}`;

  await page.goto(`${API}/#/report/${id}`);
  await expect(page.getByText("Record your decision", { exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Confirm SIF-potential" }).click();
  await expect(page.getByLabel("Rationale (required)")).toBeVisible();
  await page.getByLabel("Rationale (required)").fill(rationale);
  await page.getByLabel("Reviewer").fill("e2e.reviewer");
  await page.getByRole("button", { name: "Record decision" }).click();
  await expect(page.getByText("Confirmed SIF-potential", { exact: true })).toBeVisible();
  await expect(page.getByText(rationale, { exact: true })).toBeVisible();

  await page.goto(`${API}/#/decisions`);
  const register = page.getByRole("region", { name: "Decision & action register" }).first();
  await expect(register).toBeVisible({ timeout: 30_000 });
  await expect(register.getByText(rationale)).toBeVisible();
  await expect(register.getByText("SIF assessment").first()).toBeVisible();
  await expect(register.getByText("e2e.reviewer").first()).toBeVisible();
  await expect(register.getByText(/Who decided, when, why/)).toBeVisible();
});

test("small CSV ingest shows truthful in-flight state and the server's final counts", async ({ page }) => {
  test.setTimeout(150_000);
  const tag = uniqueTag("csv");
  const csv = buildCsv(tag, 124, "E2E Small CSV Site", "routine pump walkdown");

  await page.goto(`${API}/#/ingest`);
  await expect(page.getByRole("heading", { name: "Add a safety report" })).toBeVisible();
  await page.getByRole("tab", { name: "Import CSV" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "small-e2e.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Import small-e2e.csv?")).toBeVisible();
  await dialog.getByRole("button", { name: "Start ingest", exact: true }).click();

  const progress = page.getByRole("progressbar");
  await expect(progress).toBeVisible({ timeout: 15_000 });
  await expect(progress).toHaveAttribute("aria-valuenow", /.+/);
  await expect(page.getByText(/\d+ of 124 rows classified/)).toBeVisible();

  await expect(page.getByText("Assessment", { exact: true })).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("kpi-received")).toContainText("124");
  await expect(page.getByTestId("kpi-accepted")).toContainText("124");
  await expect(page.getByTestId("kpi-rejected")).toContainText("0");
  await expect(page.getByText("No rejected rows.", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Outcome", exact: true })).toBeVisible();
});

test("ingest job cancel: DELETE before commit cancels, after commit returns 409", async ({ request }) => {
  const csv = buildCsv(uniqueTag("cancel-ingest"), 150, "E2E Cancel Site", "routine pump walkdown");
  const accepted = await request.post(`${API}/api/ingest`, {
    data: { csv, source: "e2e" },
    timeout: 30_000,
  });
  expect(accepted.status()).toBe(202);
  const { job_id: jobId } = (await accepted.json()) as { job_id: string };

  const poll = async () => {
    const response = await request.get(`${API}/api/ingest/${jobId}`);
    expect(response.ok(), `ingest poll failed: ${response.status()}`).toBeTruthy();
    return (await response.json()) as { status: string };
  };
  const waitFor = async (statuses: string[], timeoutMs: number) => {
    const deadline = Date.now() + timeoutMs;
    let snapshot = await poll();
    while (!statuses.includes(snapshot.status) && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 50));
      snapshot = await poll();
    }
    expect(statuses, `unexpected ingest status: ${snapshot.status}`).toContain(snapshot.status);
    return snapshot;
  };

  await waitFor(["running"], 10_000);
  const cancelled = await request.delete(`${API}/api/ingest/${jobId}`);
  if (cancelled.status() === 200) {
    expect((await cancelled.json() as { status: string }).status).toBe("running");
    expect((await waitFor(["cancelled"], 10_000)).status).toBe("cancelled");
  } else {
    expect(cancelled.status(), await cancelled.text()).toBe(409);
    expect(["done", "error", "cancelled"]).toContain((await waitFor(["done", "error", "cancelled"], 30_000)).status);
  }

  expect((await request.delete(`${API}/api/ingest/${jobId}`)).status()).toBe(409);
});

test("analytics shows sample size and confidence intervals and applies its min-n guard", async ({ page }) => {
  await page.goto(`${API}/#/analytics`);
  await expect(page.getByText(/\d+ reports analysed/)).toBeVisible({ timeout: 60_000 });

  await page.getByRole("tab", { name: "Hotspots", exact: true }).click();
  const minN = page.getByLabel("Minimum reports to rank");
  await expect(minN).toBeVisible();
  await expect(page.getByText(/95% Wilson CI/).first()).toBeVisible();
  await minN.selectOption("50");
  await page.getByText(/small-n rows held out of the ranking/).click();
  await expect(page.getByText(/ — n = \d+ · Not ranked — fewer than 50 reports/).first()).toBeVisible();

  await page.getByRole("tab", { name: "Recurring patterns", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recurring patterns" })).toBeVisible();
  await expect(page.getByText(/^n \d+$/).first()).toBeVisible();
  await page.locator("article > button").first().click();
  await expect(page.getByText(/95% CI of the rate \[/).first()).toBeVisible();
  await expect(page.getByText(/no CI published for lift/).first()).toBeVisible();
});

test("footer opens the data & limitations dialog", async ({ page }) => {
  await page.goto(`${API}/#/queue`);
  await page.getByRole("button", { name: "Data & limitations" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const panel = dialog.getByRole("region", { name: "Model limitations" });
  await expect(panel).toBeAttached();
  await panel.scrollIntoViewIfNeeded();
  await expect(panel.getByText("US post-injury training proxy", { exact: true })).toBeVisible();
});

test("legacy settings route redirects and theme toggles dark mode", async ({ page }) => {
  await page.goto(`${API}/#/settings`);
  await expect(page.getByRole("heading", { name: "Add a safety report" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /^Color theme/ }).click();
  await page.getByRole("menuitemradio", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
});

test("skip link sends keyboard focus to the main-content landmark", async ({ page }) => {
  await page.goto(`${API}/#/queue`);
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
});

test("keyboard-only review reaches a recorded decision", async ({ page, request }) => {
  const tag = uniqueTag("keyboard");
  const rationale = `Keyboard review confirms the missing control was addressed. ${tag}`;
  const { id } = await seedReport(request, `A grinder disc shattered beside the workbench during maintenance ${tag}.`);

  await page.goto(`${API}/#/report/${id}`);
  await expect(page.getByText("Report detail", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Record your decision", { exact: true })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  const confirm = page.getByRole("button", { name: "Confirm SIF-potential" });
  await tabUntilFocused(page, confirm, 20);
  await expect(confirm).toBeFocused();
  await page.keyboard.press("Enter");
  const rationaleBox = page.getByLabel("Rationale (required)");
  await expect(rationaleBox).toBeVisible();
  await tabUntilFocused(page, rationaleBox, 20);
  await expect(rationaleBox).toBeFocused();
  await page.keyboard.type(rationale);
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  const submit = page.getByRole("button", { name: "Record decision" });
  await expect(submit).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Recorded decision", { exact: true })).toBeVisible();
  await expect(page.getByText(rationale, { exact: true })).toBeVisible();
});
