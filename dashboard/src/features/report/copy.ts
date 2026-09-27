/*
 * Report-detail UI strings (EN/हिं). NOTE for SHELL: @/lib/phrasebook.ts is
 * outside the REPORT slice's ownership, so these live here until they are
 * lifted into the phrasebook (mechanical move — same Pair shape, same Lang;
 * components/domain keeps its own local strings for the same reason).
 * Every user-facing string in this feature is in this file or the phrasebook;
 * source report text is always rendered unchanged.
 */
import type { Lang } from "@/lib/phrasebook";

type Pair = Record<Lang, string>;

export const COPY = {
  eyebrow: { en: "Report detail", hi: "रिपोर्ट विवरण" },
  back: { en: "Back", hi: "वापस" },
  metaActivity: { en: "Activity", hi: "गतिविधि" },
  metaContractor: { en: "Contractor", hi: "ठेकेदार" },
  metaEventDate: { en: "Event date", hi: "घटना की तारीख" },
  metaIngested: { en: "Added to register", hi: "पंजिका में जोड़ा गया" },
  metaContractorMissing: { en: "Not recorded", hi: "दर्ज नहीं" },
  dateConflation: {
    en: "If no event date was recorded, the date shown is when the report was added to the register.",
    hi: "घटना की तारीख दर्ज न होने पर रिपोर्ट को पंजिका में जोड़ने की तारीख दिखाई जाती है।",
  },
  verdictWithheld: {
    en: "Assessment unavailable because the review threshold could not be verified.",
    hi: "समीक्षा सीमा की पुष्टि न होने के कारण आकलन उपलब्ध नहीं है।",
  },
  variantScoresLabel: { en: "Variant scores", hi: "रूपांतरण स्कोर" },
  decisionHeading: { en: "Record your decision", hi: "अपना निर्णय दर्ज करें" },
  decisionRecorded: {
    en: "Decision, rationale and reviewer recorded in the audit trail.",
    hi: "निर्णय, कारण और समीक्षक ऑडिट ट्रेल में दर्ज हैं।",
  },
  chooseConfirm: { en: "Confirm SIF-potential", hi: "SIF-क्षमता की पुष्टि करें" },
  chooseNotSif: { en: "Not SIF-potential", hi: "SIF-क्षमता नहीं" },
  rationaleLabel: { en: "Rationale (required)", hi: "औचित्य (आवश्यक)" },
  rationalePlaceholder: {
    en: "Explain your decision and cite the report evidence.",
    hi: "अपने निर्णय का कारण और रिपोर्ट के साक्ष्य लिखें।",
  },
  rationaleRequired: {
    en: "Enter a rationale to record this decision.",
    hi: "निर्णय दर्ज करने के लिए कारण लिखें।",
  },
  reviewerLabel: { en: "Reviewer", hi: "समीक्षक" },
  reviewerHint: {
    en: "Name or ID recorded with the decision. Identity is self-declared, not verified by login.",
    hi: "निर्णय के साथ नाम या ID दर्ज होती है। पहचान स्वयं बताई गई है, लॉगिन से सत्यापित नहीं।",
  },
  recordDecision: { en: "Record decision", hi: "निर्णय दर्ज करें" },
  cancel: { en: "Cancel", hi: "रद्द करें" },
  recordedLabel: { en: "Recorded decision", hi: "दर्ज निर्णय" },
  recordedConfirm: {
    en: "Confirmed SIF-potential",
    hi: "SIF-क्षमता की पुष्टि की गई",
  },
  recordedNotSif: {
    en: "Recorded as not-SIF-potential",
    hi: "SIF-क्षमता नहीं के रूप में दर्ज",
  },
  recordedBy: { en: "by", hi: "द्वारा" },
  recordedNoRationale: {
    en: "No rationale recorded.",
    hi: "कारण दर्ज नहीं है।",
  },
  amend: { en: "Amend decision", hi: "निर्णय संशोधित करें" },
  amendNote: {
    en: "The correction becomes the current decision. Earlier records remain in the audit trail.",
    hi: "सुधार वर्तमान निर्णय बनेगा। पिछले रिकॉर्ड ऑडिट ट्रेल में बने रहेंगे।",
  },
  decisionFailed: {
    en: "Decision not confirmed. Check the decision log before trying again.",
    hi: "निर्णय की पुष्टि नहीं हुई। पुनः प्रयास से पहले निर्णय लॉग जाँचें।",
  },
  overridesError: {
    en: "Prior decisions unavailable. Try again before recording a new decision.",
    hi: "पिछले निर्णय उपलब्ध नहीं हैं। नया निर्णय दर्ज करने से पहले पुनः प्रयास करें।",
  },
  notFoundTitle: { en: "Report not found", hi: "रिपोर्ट नहीं मिली" },
  notFoundBody: {
    en: "This report does not exist, or it has no stored prediction to explain.",
    hi: "यह रिपोर्ट मौजूद नहीं है, या उसकी कोई संग्रहीत भविष्यवाणी नहीं है।",
  },
  loadFailedTitle: { en: "Could not load this report", hi: "यह रिपोर्ट लोड नहीं हो सकी" },
  loadFailedBody: {
    en: "Try again shortly or return to the report register.",
    hi: "कुछ देर बाद पुनः प्रयास करें या रिपोर्ट पंजिका पर लौटें।",
  },
  loadingReport: { en: "Loading report…", hi: "रिपोर्ट लोड हो रही है…" },
  retry: { en: "Retry", hi: "पुनः प्रयास" },
} as const satisfies Record<string, Pair>;

export function c(lang: Lang, key: keyof typeof COPY): string {
  return COPY[key][lang];
}

/** Barrier-failure gate labels (implementation-plan A2 gate family). The
 * gate names themselves are the API contract; labels are display only. */
export const BARRIER_LABELS: Record<string, Pair> = {
  energy_isolation_absent: { en: "Energy isolation (LOTO)", hi: "ऊर्जा पृथक्करण (LOTO)" },
  gas_test_absent: { en: "Gas test before entry", hi: "प्रवेश से पहले गैस परीक्षण" },
  permit_absent: { en: "Permit to work", hi: "परमिट टू वर्क" },
  fire_watch_absent: { en: "Fire watch", hi: "अग्नि निरीक्षक" },
  standby_absent: { en: "Standby / attendant", hi: "स्टैंडबाय / परिचारक" },
  atmosphere_unmonitored: { en: "Atmosphere monitoring", hi: "वायुमंडल निगरानी" },
  fall_protection_absent: {
    en: "Missing fall-protection anchorage",
    hi: "गिरने से बचाव का एंकर अनुपस्थित",
  },
};
