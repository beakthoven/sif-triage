/*
 * Runnable self-check for the domain's pure logic (the one check ponytail
 * asks for: fails loudly if the span math, Wilson CI, sanitiser or routing
 * rule break). Run from this directory:
 *
 *   node domain-selfcheck.ts
 *
 * Node ≥23.6 strips the type-only syntax natively; domain-logic.ts imports
 * types only (erased), so no bundler is needed.
 */

import {
  UNSTABLE_SPREAD_DEFAULT,
  effectiveWord,
  mergeSpans,
  spanSegments,
  stripVectorMath,
  wilson,
} from "./domain-logic.ts";

let failures = 0;
function check(name: string, cond: boolean): void {
  if (!cond) {
    failures += 1;
    console.error(`FAIL: ${name}`);
  } else {
    console.log(`ok: ${name}`);
  }
}

// --- wilson ---
{
  const [lo, hi] = wilson(0.5, 10);
  check("wilson(0.5,10) lo in (0.18,0.24)", lo > 0.18 && lo < 0.24);
  check("wilson(0.5,10) hi in (0.76,0.82)", hi > 0.76 && hi < 0.82);
  const [zlo, zhi] = wilson(0.0, 1);
  check("wilson(0,1) low interval", zlo === 0 && zhi < 0.8);
  const [olo, ohi] = wilson(1.0, 1);
  check("wilson(1,1) high interval", ohi === 1 && olo > 0.2);
  const [nlo, nhi] = wilson(Number.NaN, 0);
  check("wilson(nan,0) maximally uninformative", nlo === 0 && nhi === 1);
  check("wilson clamps p>1", wilson(7, 3)[0] > 0.29 && wilson(7, 3)[1] === 1);
}

// --- mergeSpans / spanSegments ---
{
  const text = "Operator removed LOTO before opening the valve. No injury occurred.";
  // Overlapping spans at real offsets ("LOTO" is at 17..21; the second span
  // overlaps it).
  const spans = [
    { start: 17, end: 21, text: "LOTO" },
    { start: 19, end: 31, text: text.slice(19, 31) },
  ];
  const merged = mergeSpans(text, spans);
  check("overlap merged into one span", merged.length === 1 && merged[0].start === 17 && merged[0].end === 31);
  check("merged span text re-sliced from source", merged[0].text === text.slice(17, 31));

  const invalid = [
    { start: 0, end: 4, text: "BOGUS" }, // text mismatch → dropped
    { start: 900, end: 910, text: "past-the-end" }, // out of range → dropped
  ];
  check("invalid spans dropped", mergeSpans(text, invalid).length === 0);

  const touching = [
    { start: 0, end: 7, text: text.slice(0, 7) },
    { start: 7, end: 15, text: text.slice(7, 15) },
  ];
  check("touching spans stay separate", mergeSpans(text, touching).length === 2);

  const segs = spanSegments(text, spans);
  check(
    "segments cover the text exactly",
    segs.map((s) => s.text).join("") === text,
  );
  check("one segment is highlighted", segs.filter((s) => s.isSpan).length === 1);
  const plain = spanSegments(text, []);
  check("no spans → single plain segment", plain.length === 1 && !plain[0].isSpan);
}

// --- stripVectorMath (the exact leak from the bug report) ---
{
  const leaked = "near-dup banner: cosine=1.000 with index row syn-cs-e-0188 (>= 0.91)";
  const cleaned = stripVectorMath(leaked);
  check("cosine leak stripped", !cleaned.includes("cosine") && !cleaned.includes("syn-cs-e-0188"));
  check("honest framing survives sanitising", !stripVectorMath("Matches a training record — memory, not generalization").includes("cosine"));
  check("max-cosine detail stripped", !stripVectorMath("max cosine=0.812").includes("0.812"));
  check("prose untouched", stripVectorMath("score 0.487 below the flag threshold — routed to review") === "score 0.487 below the flag threshold — routed to review");
}

// --- effectiveWord (unstable wording routes to REVIEW) ---
{
  const stable = { spread: 0.02, nVariants: 8 };
  const unstable = { spread: 0.31, nVariants: 8 };
  check("stable LOW stays LOW", effectiveWord("LOW", stable) === "LOW");
  check("stable CLEAR stays CLEAR", effectiveWord("CLEAR", stable) === "CLEAR");
  check("unstable LOW routes to REVIEW", effectiveWord("LOW", unstable) === "REVIEW");
  check("unstable CLEAR routes to REVIEW", effectiveWord("CLEAR", unstable) === "REVIEW");
  check("unstable HIGH stays HIGH", effectiveWord("HIGH", unstable) === "HIGH");
  check("no stability → band passes through", effectiveWord("MODERATE", null) === "MODERATE");
  check("default spread cutoff is 0.15", UNSTABLE_SPREAD_DEFAULT === 0.15);
}

if (failures > 0) {
  console.error(`\n${failures} check(s) FAILED`);
  // No `process` reference (the app tsconfig types it away): an uncaught
  // throw exits non-zero all the same.
  throw new Error(`${failures} domain-logic check(s) failed`);
}
console.log("\nall domain-logic checks passed");