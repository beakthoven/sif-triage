/* Fallback 90s demo recording — full beat flow against the LIVE :8177 stack,
 * headless Chromium at 1920x1080 with recordVideo. Silent screen capture;
 * wall-clock tight (each beat 3-6s dwell, ingest paces itself). Beats follow
 * artifacts/demo/script_90s.md order: feed settle -> green LOW -> red HIGH ->
 * density ingest money beat -> verbatim near-dup -> gray drill -> explanation
 * expander -> patterns toggle -> review tab.
 * Run: NODE_PATH=/home/dakkshesh/sih/dashboard/node_modules node runs/run2/day3/fallback_record.cjs
 * Requires pre-state restored (n_reports=4548, Kathalguri #2) — the ingest
 * button runs once per pre-state. */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const TEXTS = {
  green: "One half-inch combination spanner dropped from mast platform of drilling rig RJ-18 at Jorajan during pipe handling in the morning. It fell on the rig floor matting near V-door side. No one was standing below as floor was cleared before the job. Derrickman reminded again to use wrist lanyard for hand tools kept at height.",
  red: "During night of 18 October 2024 on rig #5, derrickman dropped a 12 inch adjustable wrench while working at monkey board, it fell past the drill floor and landed on BOP deck near two roughnecks laying pipe dope. No barricade below overhead work and wrench was not tied off. Fortunately it hit grating, not anyone. All hand tools above floor now tethered.",
  osha: "An employee was working on a swing scaffold, preparing to install terracotta tile on the exterior of a building. Terracotta tiles that had been previously installed on the building detached and fell striking the employee in the head. The employee suffered lacerations to the head, a head [OUTCOME], bleeding around the brain, and neck and back [OUTCOME].",
  drill: "Evacuation mock drill at Baghjan camp area conducted on foggy January morning at 07:30 hrs. Assembly took nine minutes due to fog and low visibility on the walkway. Two additional blinker lights suggested on muster point route. Camp manager accepted and installed the same week. Headcount procedure otherwise found satisfactory by observers.",
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const t0 = Date.now();
  const mark = (s) => console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s] ${s}`);
  const videoDir = 'runs/run2/day3/video_tmp';
  fs.rmSync(videoDir, { recursive: true, force: true });
  fs.mkdirSync(videoDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: videoDir, size: { width: 1920, height: 1080 } },
  });
  const page = await ctx.newPage();
  page.on('dialog', (d) => { mark('DIALOG: ' + d.message().slice(0, 80)); d.accept(); });

  const box = () => page.getByRole('textbox', { name: 'Classify a report' });
  const classify = async (text, dwellMs, label) => {
    await box().fill(text);
    await sleep(400);
    await page.getByRole('button', { name: 'Classify', exact: true }).click();
    await sleep(dwellMs);
    mark(label + ' card landed');
  };

  // beat 1: feed settle
  await page.goto('http://127.0.0.1:8177/', { waitUntil: 'networkidle' });
  await sleep(5000);
  mark('feed settled');

  // beat 2: contrast-green -> LOW
  await classify(TEXTS.green, 7000, 'green LOW');

  // beat 3: contrast-red -> HIGH + rule bar + WC chip
  await classify(TEXTS.red, 8000, 'red HIGH');

  // beat 4: density -> ingest -> re-rank (money beat)
  await page.getByRole('tab', { name: 'Density' }).click();
  await page.waitForSelector('td:text("Kathalguri GCS")', { timeout: 15000 });
  await sleep(3500);
  mark('density pre-state visible (Kathalguri #2)');
  await page.getByRole('button', { name: /Simulate ingest/ }).click();
  await sleep(8000); // progress bar on screen
  mark('ingest progress shown');
  await page.waitForSelector('text=just climbed to #1', { timeout: 90000 });
  await sleep(8000); // FLIP settle + delta chips
  mark('MONEY BEAT: Kathalguri #1');

  // beat 5: verbatim-osha -> near-dup banner
  await page.getByRole('tab', { name: 'Feed' }).click();
  await sleep(800);
  await classify(TEXTS.osha, 7000, 'verbatim-osha near-dup');

  // beat 6: gray drill
  await classify(TEXTS.drill, 6000, 'gray drill GATE');

  // beat 7: reopen the DUP live-paste card, open explanation expander
  await page.locator('button', { hasText: '(live paste)' }).filter({ hasText: 'DUP' }).first().click();
  await sleep(2000);
  await page.getByRole('button', { name: /Why this score\?/ }).click();
  await sleep(8000);
  mark('explanation expander open');

  // beat 8: patterns tab + kind toggle
  await page.getByRole('tab', { name: 'Patterns' }).click();
  await sleep(4500);
  await page.getByRole('tab', { name: /Activity . Barrier/ }).click();
  await sleep(4500);
  mark('patterns toggled');

  // beat 9: review tab
  await page.getByRole('tab', { name: 'Review' }).click();
  await sleep(8000);
  mark('review tab shown');

  await ctx.close();
  await browser.close();

  const vids = fs.readdirSync(videoDir).filter((f) => f.endsWith('.webm'));
  if (vids.length !== 1) throw new Error('expected 1 video, got ' + vids.length);
  const dst = 'artifacts/demo/fallback_recording.webm';
  fs.renameSync(path.join(videoDir, vids[0]), dst);
  fs.rmdirSync(videoDir);
  mark('DONE -> ' + dst + ' (total ' + ((Date.now() - t0) / 1000).toFixed(1) + 's wall)');
})().catch((e) => { console.error('RECORD FAIL:', e.message); process.exit(1); });
