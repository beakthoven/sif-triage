/* Queue feature strings (EN/हिं). Same {en, hi} shape as @/lib/phrasebook.
 * Local because lib/phrasebook.ts is SHELL-owned and carries no queue keys
 * yet; migrate these into the shell phrasebook when the shell takes over.
 * Verdict words HIGH/MODERATE/LOW stay untranslated by design: design spec §2
 * fixes them as semantic anchors paired with tokens, not free copy. */

import type { Lang } from "@/lib/phrasebook";

const QUEUE_STRINGS = {
  queueEyebrow: { en: "Report register", hi: "रिपोर्ट रजिस्टर" },
  queueTitle: { en: "Reports history", hi: "रिपोर्ट इतिहास" },
  queueSub: {
    en: "Every ingested report, most urgent first. Search and filter to find a specific event.",
    hi: "हर दर्ज रिपोर्ट, सबसे अधिक प्राथमिकता पहले। खोज और फ़िल्टर से कोई विशेष घटना पाएँ।",
  },
  addReport: { en: "Add report", hi: "रिपोर्ट जोड़ें" },
  colActivity: { en: "Activity", hi: "गतिविधि" },
  colContractor: { en: "Contractor", hi: "ठेकेदार" },
  colDate: { en: "Date", hi: "तारीख" },
  allDates: { en: "All dates", hi: "सभी तारीखें" },
  selectDateRange: { en: "Select date range", hi: "तारीख सीमा चुनें" },
  colScore: { en: "Score", hi: "स्कोर" },
  colPriority: { en: "Priority", hi: "प्राथमिकता" },
  colContext: { en: "Work context", hi: "कार्य संदर्भ" },
  scoreShort: { en: "Score", hi: "स्कोर" },
  colFlags: { en: "Flags", hi: "फ़्लैग" },
  duplicateFlag: { en: "Duplicate", hi: "डुप्लिकेट" },
  selectReport: { en: "Select report", hi: "रिपोर्ट चुनें" },
  selectAll: { en: "Select all filtered reports", hi: "सभी मेल खाती रिपोर्टें चुनें" },
  sortLabel: { en: "Sort reports", hi: "रिपोर्ट क्रम" },
  sortScoreDesc: { en: "Highest priority first", hi: "सबसे अधिक प्राथमिकता पहले" },
  sortScoreAsc: { en: "Lowest priority first", hi: "सबसे कम प्राथमिकता पहले" },
  sortIdDesc: { en: "Newest first", hi: "नवीनतम पहले" },
  sortIdAsc: { en: "Oldest first", hi: "सबसे पुरानी पहले" },
  verdictLabel: { en: "Priority", hi: "प्राथमिकता" },
  verdictAll: { en: "All priorities", hi: "सभी प्राथमिकताएँ" },
  verdictHigh: { en: "High", hi: "उच्च" },
  verdictModerate: { en: "Moderate", hi: "मध्यम" },
  verdictLow: { en: "Low", hi: "कम" },
  verdictReview: { en: "Needs manual review", hi: "मानवीय समीक्षा चाहिए" },
  verdictUnbanded: { en: "Not banded", hi: "निर्णय नहीं" },
  bandAbsentDetail: {
    en: "The API does not carry a review-priority band for this row yet — it is never derived client-side.",
    hi: "API में इस पंक्ति के लिए समीक्षा-प्राथमिकता श्रेणी अभी नहीं है — इसे क्लाइंट पर नहीं निकाला जाता।",
  },
  stabilityStable: { en: "Stable", hi: "स्थिर" },
  stabilityUnstable: { en: "Unstable", hi: "अस्थिर" },
  ruleLabel: { en: "Safety indicator", hi: "सुरक्षा संकेतक" },
  ruleAll: { en: "All indicators", hi: "सभी संकेतक" },
  ruleHint: {
    en: "Show reports matching a specific safety indicator.",
    hi: "किसी विशेष सुरक्षा संकेतक से मेल खाने वाली रिपोर्ट दिखाएँ।",
  },
  siteAll: { en: "All sites", hi: "सभी साइटें" },
  activityAll: { en: "All activities", hi: "सभी गतिविधियाँ" },
  dateFrom: { en: "From", hi: "से" },
  dateTo: { en: "To", hi: "तक" },
  clearFilters: { en: "Clear filters", hi: "सभी फ़िल्टर हटाएँ" },
  clearSearch: { en: "Clear search", hi: "खोज साफ़ करें" },
  loadingReports: { en: "Loading reports…", hi: "रिपोर्ट लोड हो रही हैं…" },
  errorTitle: {
    en: "Could not load the report register",
    hi: "रिपोर्ट रजिस्टर लोड नहीं हो सका",
  },
  errorBody: {
    en: "The full register is unavailable. Retry to load all reports.",
    hi: "पूरा रजिस्टर उपलब्ध नहीं है। सभी रिपोर्ट लोड करने के लिए पुनः प्रयास करें।",
  },
  errorPartial: {
    en: "reports loaded; incomplete list hidden",
    hi: "रिपोर्ट लोड हुईं; अधूरी सूची छिपाई गई है",
  },
  retry: { en: "Retry", hi: "पुनः प्रयास करें" },
  emptyFiltered: {
    en: "No reports match these filters.",
    hi: "इन फ़िल्टरों से कोई रिपोर्ट मेल नहीं खाती।",
  },
  emptyNone: {
    en: "No reports have been added yet. Add a report or import a CSV to begin.",
    hi: "अभी कोई रिपोर्ट नहीं जोड़ी गई। शुरू करने के लिए रिपोर्ट जोड़ें या CSV आयात करें।",
  },
  selectedLine: { en: "selected", hi: "चयनित" },
  clearSelection: { en: "Clear selection", hi: "चयन हटाएँ" },
  noFlags: { en: "No flags", hi: "कोई फ़्लैग नहीं" },
  unscored: { en: "Not scored", hi: "स्कोर नहीं" },
  ingestLegend: {
    en: "* Date added, when the event date is unavailable",
    hi: "* घटना की तारीख उपलब्ध न होने पर जोड़े जाने की तारीख",
  },
  kbdHint: {
    en: "Keyboard: ↑↓ move · Enter open",
    hi: "कीबोर्ड: ↑↓ चलें · Enter से खोलें",
  },
  gridLabel: { en: "Safety reports", hi: "सुरक्षा रिपोर्ट" },
  similarReports: { en: "{n} similar report{plural}", hi: "{n} मिलती-जुलती रिपोर्टें" },
  similarInViewTitle: {
    en: "Similar reports in this view; other cluster members are hidden by the current filters.",
    hi: "इस दृश्य में मिलती-जुलती रिपोर्टें; मौजूदा फ़िल्टर से समूह की अन्य रिपोर्टें छिपी हैं।",
  },
  similarAllTitle: {
    en: "Similar reports in this view.",
    hi: "इस दृश्य में मिलती-जुलती रिपोर्टें।",
  },
  collapseSimilar: { en: "Collapse similar reports", hi: "मिलती-जुलती रिपोर्टें समेटें" },
  compressionCaption: {
    en: "{groups} duplicate group{plural} · {reports} report{reportsPlural} collapsed",
    hi: "{groups} डुप्लिकेट समूह · {reports} रिपोर्टें समेटी गईं",
  },
  groupingUnavailable: {
    en: "Duplicate grouping is unavailable; showing every report separately.",
    hi: "डुप्लिकेट समूह उपलब्ध नहीं हैं; हर रिपोर्ट अलग दिखाई जा रही है।",
  },
  noFacet: { en: "—", hi: "—" },
} as const;

export type QueueStringKey = keyof typeof QUEUE_STRINGS;

export function tq(
  lang: Lang,
  key: QueueStringKey,
  vars?: Record<string, string | number>,
): string {
  const entry = QUEUE_STRINGS[key];
  const value = entry?.[lang] ?? entry?.en ?? key;
  return vars
    ? Object.entries(vars).reduce<string>(
        (text, [name, replacement]) => text.replaceAll(`{${name}}`, String(replacement)),
        value,
      )
    : value;
}

/** Composed count line. kept as a function because the word order differs. */
export function queueCountLine(
  lang: Lang,
  shown: number,
  loaded: number,
  indexed: number | null,
): string {
  const fmt = (n: number) => n.toLocaleString("en-IN");
  if (indexed === null) {
    return lang === "en"
      ? `${shown.toLocaleString("en-IN")} shown of ${fmt(loaded)} loaded`
      : `${fmt(loaded)} लोड, दिखा रहे हैं ${fmt(shown)}`;
  }
  return lang === "en"
    ? shown === loaded
      ? `${fmt(shown)} reports`
      : `${fmt(shown)} of ${fmt(loaded)} reports`
    : shown === loaded
      ? `${fmt(shown)} रिपोर्ट`
      : `${fmt(loaded)} में से ${fmt(shown)} रिपोर्ट`;
}

/** Honest partial-load line (never padded to look complete). */
export function queuePartialLine(lang: Lang, loaded: number): string {
  const fmt = loaded.toLocaleString("en-IN");
  return lang === "en"
    ? `${fmt} ${QUEUE_STRINGS.errorPartial.en}`
    : `${fmt} ${QUEUE_STRINGS.errorPartial.hi}`;
}