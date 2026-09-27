/**
 * E2E-3 — decision flow records a rationale and it appears in /#/decisions.
 * Fully page-driven: clears localStorage first so assertions depend only on
 * what this test did. Usage: npx tsx tests/e2e_decision.spec.ts [baseUrl]
 * Default http://127.0.0.1:8232 — never 8177.
 */
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

const NST = "NST_dec_" + process.pid + "_" + Math.random().toString(36).slice(2, 8);
fs.mkdirSync(path.join(os.tmpdir(), NST), { recursive: true });

const BASE = process.argv[2] ?? "http://127.0.0.1:8232";
const RATIONALE = `Stop-work called; excavator idle with no attendant at the north cut. NST ${Date.now()}`;

async function fetchJson(url: string): Promise<any> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}: ${await r.text()}`);
  return r.json();
}

let browser: any;
async function main(): Promise<void> {
  const reports = (await fetchJson(`${BASE}/api/reports?limit=5`)).reports;
  if (!reports?.length) throw new Error("no reports on server");
  const target = reports.find((r: any) => r.risk_score < 0.97) ?? reports[0];

  browser = await import("playwright-core").then((m) => m.chromium.launch({ executablePath: "/usr/bin/chromium", headless: true }));
  const page = await (await browser.newContext()).newPage();
  page.setDefaultTimeout(15000);

  await page.goto(`${BASE}/#/report/${target.id}`, { waitUntil: "domcontentloaded" });
  await page.evaluate(() => localStorage.removeItem("oil-sif-decisions"));

  const card = page.locator('[data-testid="decision-card"]');
  await card.waitFor();
  await card.locator("textarea").fill(RATIONALE);

  const select = card.locator("select");
  const options = await select.locator("option").all();
  const allowed = options.map((o) => ({ v: await o.getAttribute("value"), t: (await o.textContent()) ?? "" }))
    .filter((o) => o.v);
  if (!allowed.length) throw new Error("decision select has no selectable options");
  const pick = allowed[allowed.length > 1 ? 1 : 0];
  await select.selectOption(pick.v!);

  const postP = page.waitForResponse((resp) => resp.url().includes("/api/decision") && resp.request().method() === "POST");
  await card.getByRole("button", { name: /submit|record|save/i }).click();
  const resp = await postP;
  if (resp.status() >= 300) throw new Error(`decision POST failed: HTTP ${resp.status()}: ${await resp.text()}`);
  const saved = await resp.json();
  console.log(`POST ${resp.status()} -> ${JSON.stringify(saved)}`);

  const url = page.url();
  const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  if (!body.includes(pick.t.trim()))
    throw new Error(`decision ${pick.v} ("${pick.t}") absent from report page; url=${url}; body=${body.slice(0, 400)}`);
  if (!/record|saved|submit|logged/i.test(body)) throw new Error(`no recorded-confirmation on report page; url=${url}`);

  await page.goto(`${BASE}/#/decisions`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  const decisions = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  if (!decisions.includes(pick.t.trim()))
    throw new Error(`decision ${pick.v} absent from /#/decisions page`);
  if (!decisions.includes(target.id)) throw new Error(`report ${target.id} absent from /#/decisions page`);

  console.log(`PASS ${NST}: rationale recorded for report ${target.id}, decision "${pick.v}" visible on report page and in /#/decisions`);
}

main()
  .catch((e) => {
    console.error(`FAIL ${NST}:`, e.message);
    process.exit(1);
  })
  .finally(() => browser?.close());
