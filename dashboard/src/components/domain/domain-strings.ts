/*
 * Domain-string vocabulary (EN/हिं) for the explainability primitives.
 * Lives here rather than @/lib/phrasebook because phrasebook is owned by the
 * SHELL slice and this slice must not edit it — merge these keys into
 * phrasebook when the slices reconcile (flagged in the handoff).
 */

import type { Lang } from "@/lib/phrasebook";
import { t } from "@/lib/phrasebook";

export type { Lang };

const STRINGS = {
  // Verdict words — always paired with a token, never hue alone.
  wordHigh: { en: "HIGH", hi: "उच्च" },
  wordModerate: { en: "MODERATE", hi: "मध्यम" },
  wordLow: { en: "LOW", hi: "कम" },
  wordClear: { en: "CLEAR", hi: "स्पष्ट" },
  wordReview: { en: "REVIEW", hi: "समीक्षा" },
  // ScoreReadout
  reviewThreshold: { en: "Review threshold", hi: "समीक्षा सीमा" },
  serverOperatingPoint: {
    en: "server operating point — the same number on every screen",
    hi: "सर्वर ऑपरेटिंग पॉइंट — हर स्क्रीन पर वही संख्या",
  },
  modelLabel: { en: "model", hi: "मॉडल" },
  // StabilityIndicator
  stableWording: { en: "Stable wording", hi: "स्थिर शब्दावली" },
  unstableWording: { en: "Unstable wording", hi: "अस्थिर शब्दावली" },
  unstableHint: {
    en: "This score moves a lot when the same report is rephrased — treat as review priority.",
    hi: "एक ही रिपोर्ट को दूसरे शब्दों में लिखने पर स्कोर काफ़ी बदलता है — इसे समीक्षा प्राथमिकता मानें।",
  },
  scoreSpread: { en: "spread", hi: "फैलाव" },
  variantsScored: { en: "variants scored", hi: "रूपांतरण स्कोर किए" },
  verdictFlipsLabel: { en: "flips", hi: "पलटे" },
  // EvidenceText
  evidenceLabel: { en: "Evidence", hi: "साक्ष्य" },
  noEvidenceSpans: {
    en: "The model returned no evidence spans for this text — read the full report yourself.",
    hi: "मॉडल ने इस पाठ के लिए कोई साक्ष्य खंड नहीं दिया — पूरी रिपोर्ट स्वयं पढ़ें।",
  },
  // RuleBars
  ruleOutOfScope: { en: "Out of scope — not scored", hi: "दायरे से बाहर — स्कोर नहीं" },
  ruleOutOfScopeHint: {
    en: "Declared out of scope (not reliably detectable in this corpus) — shown for honesty, never faked.",
    hi: "घोषित दायरे से बाहर (इस संग्रह में विश्वसनीय रूप से नहीं पहचाना जा सकता) — ईमानदारी से दिखाया गया, कभी बनाया नहीं गया।",
  },
  ruleNoExplicitCue: {
    en: "model association — no explicit cue in text",
    hi: "मॉडल का संबंध — पाठ में स्पष्ट संकेत नहीं",
  },
  ruleNoExplicitCueHint: {
    en: "The model associates this rule with the report, but no explicit rule wording was found in the text — a reviewer should not treat it as a stated exposure.",
    hi: "मॉडल इस नियम को रिपोर्ट से जोड़ता है, लेकिन पाठ में नियम का कोई स्पष्ट उल्लेख नहीं मिला — समीक्षक इसे बताए गए जोखिम के रूप में न मानें।",
  },
  // GateList
  gatesHeading: { en: "Automated checks on this report", hi: "इस रिपोर्ट पर स्वचालित जाँचें" },
  informational: { en: "informational", hi: "सूचना" },
  gateRoutedToReview: { en: "routed to human review", hi: "मानवीय समीक्षा को भेजा गया" },
  noGatesFired: { en: "No advisory checks fired on this report.", hi: "इस रिपोर्ट पर कोई सलाहकारी जाँच नहीं चली।" },
  gateMinLength: { en: "Report too short", hi: "रिपोर्ट बहुत छोटी" },
  gateNegation: { en: "No harm reported", hi: "चोट की सूचना नहीं" },
  gateLanguage: { en: "Needs translation", hi: "अनुवाद आवश्यक" },
  gateConfidence: { en: "Unclear report", hi: "अस्पष्ट रिपोर्ट" },
  gateDrill: { en: "Drill / exercise", hi: "ड्रिल / अभ्यास" },
  gateLongInput: { en: "Long report — review full text", hi: "लंबी रिपोर्ट — पूरा पाठ जाँचें" },
  gateWellControlWatch: { en: "Well-control concern", hi: "कुएँ के नियंत्रण की चिंता" },
  gateChunkedLowScore: { en: "Possible miss — long report", hi: "संभावित चूक — लंबी रिपोर्ट" },
  gateSeverityWatch: { en: "Possible miss — serious wording", hi: "संभावित चूक — गंभीर विवरण" },
  gateVerdictStability: { en: "Verdict changes with wording", hi: "शब्द बदलने पर निर्णय बदलता है" },
  gateNearDupMeaning: {
    en: "Matches a training report — check the original details before acting.",
    hi: "प्रशिक्षण रिपोर्ट से मेल — कार्रवाई से पहले मूल विवरण जाँचें।",
  },
  gateSeverityMeaning: {
    en: "Severe wording needs a second look.",
    hi: "गंभीर शब्दावली पर दोबारा जाँच करें।",
  },
  gateChunkedMeaning: {
    en: "A long report can hide important details — review the full text.",
    hi: "लंबी रिपोर्ट में अहम विवरण छिप सकते हैं — पूरा पाठ जाँचें।",
  },
  // BarrierList
  barrierHeading: { en: "Missing safeguard", hi: "सुरक्षा उपाय अनुपस्थित" },
  barrierAbsentChip: { en: "Review", hi: "समीक्षा" },
  barrierNote: {
    en: "Sent to a reviewer.",
    hi: "समीक्षा के लिए भेजा गया।",
  },
  // VerdictCard decision footer
  decidedConfirm: { en: "Confirmed SIF-potential", hi: "SIF-क्षमता की पुष्टि की" },
  decidedReject: { en: "Marked not SIF-potential", hi: "SIF-क्षमता नहीं चिह्नित की" },
  // ExplanationBlock
  explanationTemplateLine: { en: "Model template", hi: "मॉडल टेम्पलेट" },
  // DecisionRow
  decisionWhy: { en: "Why", hi: "क्यों" },
  decisionNoRationale: { en: "No rationale recorded", hi: "कोई कारण दर्ज नहीं" },
  fieldVerdict: { en: "Verdict", hi: "निर्णय" },
  fieldRules: { en: "Rules", hi: "नियम" },
  fieldNote: { en: "Note", hi: "टिप्पणी" },
  sifPotential: { en: "SIF-potential", hi: "SIF-क्षमता" },
  notSifPotential: { en: "not SIF-potential", hi: "SIF-क्षमता नहीं" },
  blindGold: { en: "blind gold", hi: "ब्लाइंड गोल्ड" },
  // IngestProgress
  ingestCancel: { en: "Cancel", hi: "रद्द करें" },
  ingestFailedShort: { en: "Ingest stopped", hi: "इनजेस्ट रुक गया" },
  rowsUnit: { en: "rows", hi: "पंक्तियाँ" },
  ingestEta: { en: "about {s} s remaining", hi: "लगभग {s} सेकंड शेष" },
  ingestFailedHonest: {
    en: "Connection lost during ingest. Some rows may still have been saved — check the report count before retrying.",
    hi: "इनजेस्ट के दौरान कनेक्शन टूट गया। कुछ पंक्तियाँ सहेजी गई हो सकती हैं — दोबारा कोशिश से पहले रिपोर्ट संख्या जाँचें।",
  },
  // DensityTable
  colActivity: { en: "Activity", hi: "गतिविधि" },
  colContractor: { en: "Contractor", hi: "ठेकेदार" },
  densityCiHeader: { en: "Wilson 95% CI", hi: "विल्सन 95% CI" },
  densityNotRanked: { en: "Not ranked — fewer than {n} reports", hi: "क्रमबद्ध नहीं — {n} से कम रिपोर्टें" },
  densityHiddenCount: {
    en: "{c} small-n rows held out of the ranking",
    hi: "{c} छोटी-n पंक्तियाँ क्रमबद्धता से बाहर रखी गईं",
  },
  densityNoRows: { en: "No rows for this facet yet.", hi: "इस पहलू के लिए अभी कोई पंक्ति नहीं।" },
  // PatternCard
  patternRate: { en: "rate", hi: "दर" },
  patternRateCi: { en: "95% CI of the rate", hi: "दर का 95% CI" },
  patternLiftLabel: { en: "lift", hi: "लिफ्ट" },
  patternLiftNoCi: { en: "no CI published for lift", hi: "लिफ्ट का CI प्रकाशित नहीं" },
  patternLowN: { en: "low n — read with caution", hi: "कम n — सावधानी से पढ़ें" },
  // LimitationsPanel
  limitationsHeading: { en: "Known limitations", hi: "ज्ञात सीमाएँ" },
  limitationsNote: { en: "Stated before you ask.", hi: "आपके पूछने से पहले।" },
} as const;

export type DomainStringKey = keyof typeof STRINGS;

export function dt(lang: Lang, key: DomainStringKey, vars?: Record<string, string | number>): string {
  const s: string = STRINGS[key][lang];
  if (!vars) return s;
  return Object.entries(vars).reduce<string>(
    (acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)),
    s,
  );
}

/** Human label for a gate slug — never renders the slug itself. near_dup's
 *  reviewer copy comes from the phrasebook (honest framing, no vector math,
 *  no training-row ids). Unknown gate names (future gate work) get a
 *  prettified label, not internals. */
export function gateLabel(name: string, lang: Lang): string {
  if (name === "near_dup") return t(lang, "nearDupBanner");
  const key = GATE_LABEL_KEYS[name];
  if (key) return dt(lang, key);
  return name.replace(/[_-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

const GATE_LABEL_KEYS: Record<string, DomainStringKey> = {
  min_length: "gateMinLength",
  negation: "gateNegation",
  language: "gateLanguage",
  confidence: "gateConfidence",
  drill: "gateDrill",
  long_input: "gateLongInput",
  well_control_watch: "gateWellControlWatch",
  chunked_low_score: "gateChunkedLowScore",
  severity_watch: "gateSeverityWatch",
  verdict_stability: "gateVerdictStability",
};