/* UI-chrome phrasebook only (EN/हिं). Report text is NEVER machine-translated
 * live — it stays original with a "translation available" badge. Scope: ~15
 * strings, dev-time cloud-QA'd. */

export type Lang = "en" | "hi";

const STRINGS = {
  appTitle: { en: "SIF-Precursor Detection Engine", hi: "SIF-पूर्वसंकेत पहचान इंजन" },
  appSub: { en: "OIL India · Triage Console", hi: "OIL इंडिया · ट्रायाज कंसोल" },
  tabFeed: { en: "Feed", hi: "फ़ीड" },
  tabDensity: { en: "Density", hi: "घनत्व" },
  tabPatterns: { en: "Patterns", hi: "पैटर्न" },
  tabReview: { en: "Review", hi: "समीक्षा" },
  confirm: { en: "Confirm SIF-potential", hi: "SIF-क्षमता की पुष्टि करें" },
  notSif: { en: "Not SIF-potential", hi: "SIF-क्षमता नहीं" },
  flaggedFor: { en: "Flagged for HSE review", hi: "HSE समीक्षा के लिए चिह्नित" },
  noAction: { en: "no action needed", hi: "कोई कार्रवाई आवश्यक नहीं" },
  ruleProbs: { en: "Rule probabilities", hi: "नियम प्रायिकताएँ" },
  footer: {
    en: "Model proposes, HSE disposes. Your decision becomes a training label.",
    hi: "मॉडल प्रस्तावित करता है — HSE निपटान करता है। आपका निर्णय प्रशिक्षण लेबल बनता है।",
  },
  triageScore: { en: "triage score", hi: "ट्रायाज स्कोर" },
  rerank: { en: "Simulate ingest → re-rank", hi: "इनजेस्ट → पुनः रैंक" },
  ingesting: { en: "Ingesting reports…", hi: "रिपोर्ट इनजेस्ट हो रही हैं…" },
  ingestedDone: { en: "Batch ingested — re-ranked", hi: "बैच इनजेस्ट — पुनः रैंक" },
  ingestConfirm: {
    en: "Ingest the 6-report Baghjan demo batch into the LIVE database? The API dedups exact repeats — this runs once per session.",
    hi: "6-रिपोर्ट बाघजान डेमो बैच LIVE डेटाबेस में इनजेस्ट करें? API सटीक दोहराव डीडुप करता है — प्रति सत्र एक बार।",
  },
  ingestFailed: {
    en: "Ingest failed — live data unchanged. Check the API and retry.",
    hi: "इनजेस्ट विफल — लाइव डेटा अपरिवर्तित। API जाँचें, पुनः प्रयास करें।",
  },
  awaiting: { en: "Awaiting HSE disposition", hi: "HSE निपटान की प्रतीक्षा में" },
  overrides: { en: "Logged overrides", hi: "दर्ज ओवरराइड" },
  translationAvailable: { en: "translation available", hi: "अनुवाद उपलब्ध" },
  reportQueue: { en: "Report queue", hi: "रिपोर्ट कतार" },
  whyScore: { en: "Why this score?", hi: "यह स्कोर क्यों?" },
  nearDupBanner: {
    en: "Matches a training record — memory, not generalization",
    hi: "प्रशिक्षण रिकॉर्ड से मेल — सामान्यीकरण नहीं, स्मृति",
  },
  chunkedBadge: { en: "CHUNKED · sliding-window scoring", hi: "CHUNKED · स्लाइडिंग-विंडो स्कोरिंग" },
  llmPhrased: { en: "phrased by local LLM", hi: "स्थानीय LLM द्वारा पुनर्लिखित" },
  pasteTitle: { en: "Classify a report", hi: "रिपोर्ट वर्गीकृत करें" },
  pastePlaceholder: {
    en: "Paste a UA/UC or near-miss report here…",
    hi: "UA/UC या नियर-मिस रिपोर्ट यहाँ पेस्ट करें…",
  },
  pasteButton: { en: "Classify", hi: "वर्गीकृत करें" },
  pasteBusy: { en: "Classifying…", hi: "वर्गीकरण जारी…" },
  pasteHint: { en: "Ctrl+Enter to classify", hi: "Ctrl+Enter से वर्गीकृत करें" },
  liveChip: { en: "LIVE", hi: "लाइव" },
  offlineNote: {
    en: "API unreachable — offline placeholder, not a score",
    hi: "API अनुपलब्ध — ऑफ़लाइन प्लेसहोल्डर, स्कोर नहीं",
  },
} as const;

export type StringKey = keyof typeof STRINGS;

export function t(lang: Lang, key: StringKey): string {
  return STRINGS[key][lang];
}
