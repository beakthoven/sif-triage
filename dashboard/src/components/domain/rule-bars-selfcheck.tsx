import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { RuleScore } from "@/lib/types";
import { RuleBars } from "./rule-bars";

const rules: RuleScore[] = [
  { code: "line_of_fire", name: "Line of Fire", prob: 0.7, in_scope: true, cue_hit: null },
  { code: "work_authorisation", name: "Work Authorisation (Permit to Work)", prob: 0, in_scope: false, cue_hit: null },
  { code: "bypassing_safety_controls", name: "Bypassing Safety Controls", prob: 0, in_scope: false, cue_hit: null },
];
const markup = renderToStaticMarkup(createElement(RuleBars, { rules, lang: "en" }));
if (!markup.includes("Line of Fire") || markup.includes("Work Authorisation") || markup.includes("Bypassing Safety Controls")) {
  throw new Error(`RuleBars out-of-scope contract failed: ${markup}`);
}
console.log("RuleBars scope self-check: PASS");
