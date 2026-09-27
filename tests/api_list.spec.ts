/**
 * API gate tests — queue list (WAVE2 API-1): band containment, descending
 * score order, limit honored. Request-scoped tmp dir so concurrent API agents
 * share nothing. Usage: npx tsx tests/api_list.spec.ts [baseUrl]
 * Default http://127.0.0.1:8233 — never 8177.
 */
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

const NST = "NST_list_" + process.pid + "_" + Math.random().toString(36).slice(2, 8);
fs.mkdirSync(path.join(os.tmpdir(), NST), { recursive: true });

const BASE = process.argv[2] ?? "http://127.0.0.1:8233";

async function fetchJson(url: string): Promise<any> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}: ${await r.text()}`);
  return r.json();
}

async function main(): Promise<void> {
  const health = await fetchJson(`${BASE}/api/health`);
  if (health?.classifier !== "RealOnnxClassifier")
    throw new Error(`expected RealOnnxClassifier, got ${JSON.stringify(health?.classifier)}`);

  const data = await fetchJson(`${BASE}/api/reports?band=SIF&limit=10`);
  const rows: Array<Record<string, any>> = data.reports;
  assert(Array.isArray(rows) && rows.length > 0, "no reports returned");

  const outside = rows.filter((rp) => rp.risk_band !== "SIF");
  assert(outside.length === 0, "rows outside requested band: " + JSON.stringify(outside.map((r) => r.id)));

  const scores = rows.map((rp) => Number(rp.risk_score));
  assert(
    scores.every((s, i) => i === 0 || scores[i - 1] >= s),
    "scores not descending: " + JSON.stringify(scores)
  );

  const paged = await fetchJson(`${BASE}/api/reports?band=SIF&limit=3`);
  assert(paged.reports.length === 3, `limit=3 returned ${paged.reports.length} rows`);

  console.log(`PASS ${NST}: band containment, descending order, limit honored`);
}

function assert(cond: boolean, msg: string): void {
  if (!cond) {
    console.error(`FAIL ${NST}:`, msg);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(`FAIL ${NST}:`, e.message);
  process.exit(1);
});
