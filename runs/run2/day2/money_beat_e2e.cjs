/* Money-beat E2E v2 on the LIVE :8177 stack (own headless browser — the MCP
 * browser is shared with other audit agents). Fixes vs v1: waits for LIVE
 * data (the table initially renders the mock snapshot), measures the ingest
 * POST duration separately from render/settle. */
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('dialog', (d) => { console.log('DIALOG:', d.message().slice(0, 110)); d.accept(); });

  await page.goto('http://127.0.0.1:8177/', { waitUntil: 'networkidle' });
  await page.getByRole('tab', { name: 'Density' }).click();
  // The table renders DENSITY_BEFORE (mock) instantly, then the live fetch
  // swaps in — wait for a key that exists only in the live pre-state.
  await page.waitForSelector('td:text("Kathalguri GCS")', { timeout: 15000 });
  await page.waitForTimeout(400);

  const readTop = () => page.$$eval('table tbody tr', (trs) =>
    trs.slice(0, 5).map((tr) => [...tr.querySelectorAll('td')].map((td) => td.textContent.trim()).join(' | ')));

  const before = await readTop();
  console.log('BEFORE (live):'); before.forEach((r) => console.log('  ' + r));
  await page.screenshot({ path: 'runs/run2/day2/money_beat_before.png', fullPage: false });

  const t0 = Date.now();
  const respP = page.waitForResponse((r) => r.url().includes('/api/ingest'), { timeout: 120000 });
  await page.getByRole('button', { name: /Simulate ingest/ }).click();
  await page.waitForTimeout(6000);
  await page.screenshot({ path: 'runs/run2/day2/money_beat_progress.png' });
  const resp = await respP;
  const postWall = (Date.now() - t0) / 1000;
  console.log('POST /api/ingest ->', resp.status(), 'wall', postWall.toFixed(1) + 's');
  console.log('ingest result:', JSON.stringify(await resp.json().then(({ report_ids, ...rest }) => rest)));

  await page.waitForSelector('text=just climbed to #1', { timeout: 30000 });
  await page.waitForTimeout(1800); // FLIP settle
  const wall = (Date.now() - t0) / 1000;
  const after = await readTop();
  console.log('AFTER:'); after.forEach((r) => console.log('  ' + r));
  console.log('BEAT WALL (click -> settled re-rank):', wall.toFixed(1) + 's');
  const health = await (await page.request.get('http://127.0.0.1:8177/api/health')).json();
  console.log('health after:', JSON.stringify(health));
  await page.screenshot({ path: 'runs/run2/day2/money_beat_after.png', fullPage: false });
  await browser.close();
})().catch((e) => { console.error('E2E FAIL:', e.message); process.exit(1); });
