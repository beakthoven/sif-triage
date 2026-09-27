/* DECISIONS feature strings — EN/हिं, same {en, hi} shape as @/lib/phrasebook.
 * Kept inside the feature slice (lib/** is SHELL's); keys are prefixed "dec"
 * so a future merge into the phrasebook cannot collide. */
import type { Lang } from "@/lib/phrasebook";

const STRINGS = {
  decTitle: { en: "Decision & action register", hi: "निर्णय एवं कार्रवाई पंजिका" },
  decEyebrow: { en: "Audit trail", hi: "ऑडिट ट्रेल" },
  decPageTitle: { en: "Decision log", hi: "निर्णय लॉग" },
  reviewerCardTitle: { en: "Reviewer identity", hi: "समीक्षक पहचान" },
  metricsFlagRate: { en: "flag rate", hi: "चिह्नित दर" },
  decSub: {
    en: "Who decided, when, why — and whether the action closed.",
    hi: "किसने तय किया, कब, क्यों — और कार्रवाई बंद हुई या नहीं।",
  },
  colReport: { en: "Report", hi: "रिपोर्ट" },
  colField: { en: "Field", hi: "फ़ील्ड" },
  colWas: { en: "Was", hi: "पहले" },
  colNow: { en: "Now", hi: "अब" },
  colReviewer: { en: "Reviewer", hi: "समीक्षक" },
  colWhen: { en: "When", hi: "समय" },
  colSeverity: { en: "Severity", hi: "गंभीरता" },
  colRationale: { en: "Rationale", hi: "कारण" },
  colActions: { en: "Actions", hi: "कार्रवाई" },
  recordsWord: { en: "records", hi: "रिकॉर्ड" },
  rationaleNone: { en: "Not recorded", hi: "दर्ज नहीं" },
  correct: { en: "Correct", hi: "सुधारें" },
  capaBtn: { en: "CAPA", hi: "CAPA" },
  superseded: { en: "Superseded", hi: "प्रतिस्थापित" },
  bandHigh: { en: "High priority", hi: "उच्च प्राथमिकता" },
  bandModerate: { en: "Moderate priority", hi: "मध्यम प्राथमिकता" },
  bandLow: { en: "Low priority", hi: "कम प्राथमिकता" },
  bandUnknown: { en: "Review priority unavailable", hi: "समीक्षा प्राथमिकता अनुपलब्ध" },
  fieldSifLabel: { en: "SIF assessment", hi: "SIF मूल्यांकन" },
  fieldRules: { en: "Rule tags", hi: "नियम टैग" },
  fieldNotes: { en: "Note", hi: "टिप्पणी" },
  valSifPotential: { en: "SIF-potential", hi: "SIF-क्षमता" },
  valNotSifPotential: { en: "Not SIF-potential", hi: "SIF-क्षमता नहीं" },
  bandNote: { en: "band (legacy)", hi: "बैंड (पुराना)" },
  reviewerHeading: { en: "Recording decisions as", hi: "निर्णय दर्ज हो रहे हैं इनके नाम से" },
  reviewerHint: {
    en: "Recorded with each correction. Reviewer identity is self-declared, not verified by login.",
    hi: "हर सुधार के साथ दर्ज होता है। समीक्षक की पहचान स्वयं बताई गई है, लॉगिन से सत्यापित नहीं।",
  },
  reviewerPlaceholder: { en: "e.g. a.boruah (HSE)", hi: "जैसे: a.boruah (HSE)" },
  reviewerRequired: { en: "Enter the reviewer name first.", hi: "पहले समीक्षक का नाम दर्ज करें।" },
  exportBtn: { en: "Export NDJSON", hi: "NDJSON निर्यात" },
  exportHint: {
    en: "Latest decision for each report and field, with links to earlier records. CAPA details are not included.",
    hi: "हर रिपोर्ट और फ़ील्ड का नवीनतम निर्णय, पिछले रिकॉर्ड के संदर्भ सहित। CAPA विवरण शामिल नहीं हैं।",
  },
  exportOk: { en: "records exported", hi: "रिकॉर्ड निर्यात हुए" },
  exportFail: { en: "Export unavailable. Try again shortly.", hi: "निर्यात उपलब्ध नहीं है। कुछ देर बाद पुनः प्रयास करें।" },
  metricsTitle: { en: "Metrics summary", hi: "मापदंड सारांश" },
  metricsUnavailable: { en: "Metrics unavailable.", hi: "मापदंड उपलब्ध नहीं हैं।" },
  metricsReports: { en: "reports", hi: "रिपोर्ट" },
  metricsFlagged: { en: "flagged", hi: "चिह्नित" },
  metricsOverrides: { en: "decisions", hi: "निर्णय" },
  workloadTitle: { en: "Reviewer workload", hi: "समीक्षक कार्यभार" },
  workloadOpen: { en: "Open CAPA", hi: "खुले CAPA" },
  workloadProgress: { en: "In progress", hi: "प्रगति पर" },
  workloadClosed: { en: "Closed", hi: "बंद" },
  workloadNoCapa: { en: "Decisions without CAPA", hi: "CAPA के बिना निर्णय" },
  workloadFirAged: { en: "FIR overdue (24 h)", hi: "FIR समय-सीमा पार (24 घंटे)" },
  workloadIirAged: { en: "IIR overdue (30 d)", hi: "IIR समय-सीमा पार (30 दिन)" },
  workloadByOwner: { en: "Open items by owner", hi: "जिम्मेदार व्यक्ति के अनुसार खुली कार्रवाइयाँ" },
  workloadNote: {
    en: "OISD deadlines: first information report within 24 hours; investigation report within 30 days. Check the suggested track. CAPA details stay in this browser and are not shared with other reviewers.",
    hi: "OISD समय-सीमाएँ: प्रथम सूचना रिपोर्ट 24 घंटे में; जाँच रिपोर्ट 30 दिनों में। सुझाया ट्रैक जाँचें। CAPA विवरण केवल इस ब्राउज़र में रहते हैं और अन्य समीक्षकों से साझा नहीं होते।",
  },
  capaTitle: { en: "CAPA action", hi: "CAPA कार्रवाई" },
  capaDesc: {
    en: "Assign an owner, due date and status. Changes are saved in this browser only.",
    hi: "जिम्मेदार व्यक्ति, नियत तिथि और स्थिति दर्ज करें। बदलाव केवल इस ब्राउज़र में सहेजे जाते हैं।",
  },
  ownerLabel: { en: "Owner", hi: "जिम्मेदार व्यक्ति" },
  ownerRequired: { en: "Owner is required.", hi: "जिम्मेदार व्यक्ति का नाम आवश्यक है।" },
  dueLabel: { en: "Due date", hi: "नियत तिथि" },
  statusLabel: { en: "Status", hi: "स्थिति" },
  trackLabel: { en: "OISD track", hi: "OISD ट्रैक" },
  trackFir: { en: "FIR: major incident, 24 h", hi: "FIR: बड़ी घटना, 24 घंटे" },
  trackIir: { en: "IIR: investigation, 30 days", hi: "IIR: जाँच, 30 दिन" },
  statusOpen: { en: "Open", hi: "खुला" },
  statusInProgress: { en: "In progress", hi: "प्रगति पर" },
  statusClosed: { en: "Closed", hi: "बंद" },
  capaSave: { en: "Save CAPA", hi: "CAPA सहेजें" },
  capaSaved: { en: "CAPA saved in this browser.", hi: "CAPA इस ब्राउज़र में सहेजा गया।" },
  amendTitle: { en: "Correct this decision", hi: "इस निर्णय को सुधारें" },
  amendNotice: {
    en: "The correction becomes the current decision. Earlier records remain in the audit trail.",
    hi: "सुधार वर्तमान निर्णय बनेगा। पिछले रिकॉर्ड ऑडिट ट्रेल में बने रहेंगे।",
  },
  amendField: { en: "Field", hi: "फ़ील्ड" },
  amendNewValue: { en: "New value", hi: "नया मान" },
  ruleOutOfScope: { en: " (out of scope)", hi: " (दायरे से बाहर)" },
  rationaleLabel: { en: "Rationale (mandatory)", hi: "कारण (अनिवार्य)" },
  rationaleHint: {
    en: "Explain the correction and cite the report evidence.",
    hi: "सुधार का कारण और रिपोर्ट के साक्ष्य लिखें।",
  },
  rationaleError: { en: "A rationale is required for every correction.", hi: "हर सुधार के लिए कारण अनिवार्य है।" },
  valueError: { en: "A value is required.", hi: "मान अनिवार्य है।" },
  amendSubmit: { en: "Record correction", hi: "सुधार दर्ज करें" },
  amendFail: { en: "Correction not confirmed. Check the decision log before trying again.", hi: "सुधार की पुष्टि नहीं हुई। पुनः प्रयास से पहले निर्णय लॉग जाँचें।" },
  amendOk: { en: "Correction recorded.", hi: "सुधार दर्ज हुआ।" },
  cancel: { en: "Cancel", hi: "रद्द करें" },
  emptyTitle: { en: "No decisions recorded yet", hi: "अभी कोई निर्णय दर्ज नहीं" },
  emptyBody: {
    en: "Review a report to record the first decision.",
    hi: "पहला निर्णय दर्ज करने के लिए रिपोर्ट की समीक्षा करें।",
  },
  openReports: { en: "Open Reports History", hi: "रिपोर्ट इतिहास खोलें" },
  offlineChip: { en: "Sample data", hi: "नमूना डेटा" },
  offlineNote: {
    en: "Live decisions unavailable. These are sample records.",
    hi: "लाइव निर्णय उपलब्ध नहीं हैं। ये नमूना रिकॉर्ड हैं।",
  },
  loadingLabel: { en: "Loading decision log…", hi: "निर्णय रिकॉर्ड लोड हो रहा है…" },
  loadFailed: { en: "Decision log unavailable", hi: "निर्णय लॉग उपलब्ध नहीं है" },
  retry: { en: "Retry", hi: "पुनः प्रयास" },
  snippetNone: { en: "Report text unavailable", hi: "रिपोर्ट पाठ अनुपलब्ध" },
  overdue: { en: "Overdue", hi: "अतिदेय" },
  capaDue: { en: "due", hi: "नियत" },
  loadingSnippet: { en: "loading report…", hi: "रिपोर्ट लोड हो रही है…" },
} as const;

export type DecKey = keyof typeof STRINGS;

export function dt(lang: Lang, key: DecKey): string {
  return STRINGS[key][lang];
}

/** Locale-aware timestamp (IST-style medium date + short time). */
export function fmtWhen(lang: Lang, iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(lang === "hi" ? "hi-IN" : "en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/** yyyy-mm-dd for <input type="date">. */
export function fmtDue(lang: Lang, yyyyMmDd: string): string {
  const d = new Date(`${yyyyMmDd}T00:00:00`);
  if (Number.isNaN(d.getTime())) return yyyyMmDd;
  return d.toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", { dateStyle: "medium" });
}
