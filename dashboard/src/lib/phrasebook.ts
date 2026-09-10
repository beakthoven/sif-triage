/* UI-chrome phrasebook only (EN/हिं). Report text is NEVER machine-translated
 * live — it stays original with a "translation available" badge. The original
 * 33 keys are stable (dev-time cloud-QA'd); demo-day product pass added
 * plain-words keys at the bottom in the same style. */

export type Lang = "en" | "hi";

const STRINGS = {
  appTitle: { en: "Safety Report Triage", hi: "सुरक्षा रिपोर्ट ट्रायाज" },
  appSub: { en: "OIL India", hi: "OIL इंडिया" },
  tabFeed: { en: "Feed", hi: "फ़ीड" },
  tabDensity: { en: "Density", hi: "घनत्व" },
  tabPatterns: { en: "Patterns", hi: "पैटर्न" },
  tabReview: { en: "Review", hi: "समीक्षा" },
  confirm: { en: "Confirm SIF-potential", hi: "SIF-क्षमता की पुष्टि करें" },
  notSif: { en: "Not SIF-potential", hi: "SIF-क्षमता नहीं" },
  flaggedFor: { en: "Flagged for HSE review", hi: "HSE समीक्षा के लिए चिह्नित" },
  noAction: { en: "no action needed", hi: "कोई कार्रवाई आवश्यक नहीं" },
  ruleProbs: { en: "Matching life-saving rules", hi: "मेल खाते जीवन-रक्षक नियम" },
  footer: {
    en: "Model proposes, HSE disposes. Your decision becomes a training label.",
    hi: "मॉडल प्रस्तावित करता है — HSE निपटान करता है। आपका निर्णय प्रशिक्षण लेबल बनता है।",
  },
  triageScore: { en: "triage score", hi: "ट्रायाज स्कोर" },
  rerank: { en: "Simulate ingest → re-rank", hi: "इनजेस्ट → पुनः रैंक" },
  ingesting: { en: "Ingesting reports…", hi: "रिपोर्ट इनजेस्ट हो रही हैं…" },
  ingestedDone: { en: "Batch ingested — re-ranked", hi: "बैच इनजेस्ट — पुनः रैंक" },
  ingestConfirm: {
    en: "Ingest the 500-report demo batch? Real classification, about 15 seconds. This runs once per session.",
    hi: "500-रिपोर्ट डेमो बैच इनजेस्ट करें? वास्तविक वर्गीकरण, लगभग 15 सेकंड। प्रति सत्र एक बार।",
  },
  ingestFailed: {
    en: "Ingest failed — live data unchanged. Check the API and retry.",
    hi: "इनजेस्ट विफल — लाइव डेटा अपरिवर्तित। API जाँचें, पुनः प्रयास करें।",
  },
  awaiting: { en: "Awaiting your review", hi: "आपकी समीक्षा की प्रतीक्षा में" },
  overrides: { en: "Logged overrides", hi: "दर्ज ओवरराइड" },
  translationAvailable: { en: "translation available", hi: "अनुवाद उपलब्ध" },
  reportQueue: { en: "Report queue", hi: "रिपोर्ट कतार" },
  whyScore: { en: "Why this score?", hi: "यह स्कोर क्यों?" },
  nearDupBanner: {
    en: "Matches a training record — memory, not generalization",
    hi: "प्रशिक्षण रिकॉर्ड से मेल — सामान्यीकरण नहीं, स्मृति",
  },
  chunkedBadge: { en: "Scored in sections — long report", hi: "खंडों में स्कोर — लंबी रिपोर्ट" },
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
  // Product-lens additions (demo-day declutter): plain-words chrome.
  statusOnline: { en: "Online", hi: "ऑनलाइन" },
  statusOffline: { en: "Offline demo", hi: "ऑफ़लाइन डेमो" },
  reportsIndexed: { en: "reports indexed", hi: "रिपोर्ट अनुक्रमित" },
  oosNote: {
    en: "Cannot be judged from report text",
    hi: "रिपोर्ट के पाठ से निर्णय संभव नहीं",
  },
  densitySub: {
    en: "Sites ranked by flagged near-miss density — where to inspect next",
    hi: "चिह्नित नियर-मिस घनत्व से क्रमित साइटें — अगला निरीक्षण कहाँ",
  },
  overridesNote: {
    en: "Your decisions become training examples",
    hi: "आपके निर्णय प्रशिक्षण उदाहरण बनते हैं",
  },
  colReport: { en: "Report", hi: "रिपोर्ट" },
  colField: { en: "Field", hi: "फ़ील्ड" },
  colWas: { en: "Was", hi: "पहले" },
  colNow: { en: "Now", hi: "अब" },
  colReviewer: { en: "Reviewer", hi: "समीक्षक" },
  colWhen: { en: "When", hi: "समय" },
} as const;

export type StringKey = keyof typeof STRINGS;

export function t(lang: Lang, key: StringKey): string {
  return STRINGS[key][lang];
}
