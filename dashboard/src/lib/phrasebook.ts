/* UI chrome only (EN/हिं). Source reports are always shown unchanged. */

export type Lang = "en" | "hi";

const STRINGS = {
  appTitle: { en: "EcharikAI", hi: "EcharikAI" },
  appTitleShort: { en: "EcharikAI", hi: "EcharikAI" },
  appSub: { en: "OIL India", hi: "OIL इंडिया" },
  tabTriage: { en: "Reports History", hi: "रिपोर्ट इतिहास" },
  tabInsights: { en: "Risk Trends", hi: "जोखिम रुझान" },
  tabDecisions: { en: "Decision Log", hi: "निर्णय लॉग" },
  tabHistory: { en: "Decision history", hi: "निर्णय इतिहास" },
  workspaceTriage: { en: "Review the reports that need attention", hi: "ध्यान देने योग्य रिपोर्टों की समीक्षा करें" },
  workspaceTriageSub: {
    en: "Priorities, evidence and human decisions in one queue.",
    hi: "प्राथमिकता, साक्ष्य और मानवीय निर्णय — एक ही कतार में।",
  },
  workspaceInsights: { en: "Where should the HSE team focus next?", hi: "HSE टीम को आगे कहाँ ध्यान देना चाहिए?" },
  workspaceDecisions: { en: "Decision history", hi: "निर्णय इतिहास" },
  confirm: { en: "Confirm SIF-potential", hi: "SIF-क्षमता की पुष्टि करें" },
  notSif: { en: "Not SIF-potential", hi: "SIF-क्षमता नहीं" },
  flaggedFor: { en: "Flagged for HSE review", hi: "HSE समीक्षा के लिए चिह्नित" },
  noAction: { en: "Low review priority", hi: "कम समीक्षा प्राथमिकता" },
  highPriority: { en: "High review priority", hi: "उच्च समीक्षा प्राथमिकता" },
  moderatePriority: { en: "Moderate review priority", hi: "मध्यम समीक्षा प्राथमिकता" },
  ruleProbs: { en: "Matching life-saving rules", hi: "मेल खाते जीवन-रक्षक नियम" },
  footer: {
    en: "AI supports review. HSE makes the final decision.",
    hi: "AI समीक्षा में सहायता करता है। अंतिम निर्णय HSE लेता है।",
  },
  triageScore: { en: "triage score", hi: "ट्रायाज स्कोर" },
  rerank: { en: "Run demo batch", hi: "डेमो बैच चलाएँ" },
  importCsv: { en: "Import CSV", hi: "CSV आयात करें" },
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
  awaiting: { en: "Needs review", hi: "समीक्षा आवश्यक" },
  overrides: { en: "Recorded decisions", hi: "दर्ज निर्णय" },
  reportQueue: { en: "Work queue", hi: "कार्य कतार" },
  whyScore: { en: "What this means", hi: "इसका मतलब" },
  nearDupBanner: {
    en: "Possible training-report match",
    hi: "प्रशिक्षण रिपोर्ट से संभावित मेल",
  },
  chunkedBadge: { en: "Scored in sections — long report", hi: "खंडों में स्कोर — लंबी रिपोर्ट" },
  llmPhrased: { en: "phrased by local LLM", hi: "स्थानीय LLM द्वारा पुनर्लिखित" },
  pasteTitle: { en: "Classify a report", hi: "रिपोर्ट वर्गीकृत करें" },
  pastePlaceholder: {
    en: "Describe the event, what was observed and any immediate action taken…",
    hi: "घटना, जो देखा गया और की गई तत्काल कार्रवाई का विवरण दें…",
  },
  pasteButton: { en: "Review Report", hi: "रिपोर्ट की समीक्षा करें" },
  pasteBusy: { en: "Reviewing…", hi: "समीक्षा जारी…" },
  pasteHint: { en: "Ctrl+Enter to classify", hi: "Ctrl+Enter से वर्गीकृत करें" },
  liveChip: { en: "LIVE", hi: "लाइव" },
  offlineNote: {
    en: "API unreachable — offline placeholder, not a score",
    hi: "API अनुपलब्ध — ऑफ़लाइन प्लेसहोल्डर, स्कोर नहीं",
  },
  statusOnline: { en: "Online", hi: "ऑनलाइन" },
  statusOffline: { en: "Offline demo", hi: "ऑफ़लाइन डेमो" },
  reportsIndexed: { en: "reports indexed", hi: "रिपोर्ट अनुक्रमित" },
  densitySub: {
    en: "Sites ranked by flagged near-miss density — where to inspect next",
    hi: "चिह्नित नियर-मिस घनत्व से क्रमित साइटें — अगला निरीक्षण कहाँ",
  },
  overridesNote: {
    en: "An audit trail of HSE review outcomes",
    hi: "HSE समीक्षा परिणामों का ऑडिट रिकॉर्ड",
  },
  colReport: { en: "Report", hi: "रिपोर्ट" },
  colField: { en: "Field", hi: "फ़ील्ड" },
  colWas: { en: "Was", hi: "पहले" },
  colNow: { en: "Now", hi: "अब" },
  colReviewer: { en: "Reviewer", hi: "समीक्षक" },
  colWhen: { en: "When", hi: "समय" },
  filterAll: { en: "All reports", hi: "सभी रिपोर्ट" },
  filterPriority: { en: "Priority queue", hi: "प्राथमिकता कतार" },
  filterReview: { en: "Needs decision", hi: "निर्णय आवश्यक" },
  filterReviewed: { en: "Reviewed", hi: "समीक्षित" },
  filterInformational: { en: "No review needed", hi: "समीक्षा आवश्यक नहीं" },
  filterDuplicate: { en: "Duplicates", hi: "डुप्लिकेट" },
  searchReports: { en: "Search reports", hi: "रिपोर्ट खोजें" },
  noMatchingReports: { en: "No reports match these filters.", hi: "इन फ़िल्टरों से कोई रिपोर्ट मेल नहीं खाती।" },
  manualReview: { en: "Manual review required", hi: "मानवीय समीक्षा आवश्यक" },
  technicalDetail: { en: "Technical detail", hi: "तकनीकी विवरण" },
  decisionSaved: { en: "Decision recorded", hi: "निर्णय दर्ज हुआ" },
  alreadyReviewed: { en: "Reviewed by HSE", hi: "HSE द्वारा समीक्षित" },
  recordOutcome: { en: "Record review outcome", hi: "समीक्षा परिणाम दर्ज करें" },
  optionalReview: {
    en: "Optional — record an outcome only when this report is formally reviewed.",
    hi: "वैकल्पिक — परिणाम तभी दर्ज करें जब रिपोर्ट की औपचारिक समीक्षा हो।",
  },
  priorityGuidance: {
    en: "Work from the top as capacity allows. These are recommendations, not mandatory confirmations.",
    hi: "उपलब्ध क्षमता के अनुसार ऊपर से काम करें। ये सुझाव हैं, अनिवार्य पुष्टि नहीं।",
  },
  locations: { en: "Locations", hi: "स्थान" },
  recurringPatterns: { en: "Recurring patterns", hi: "दोहराते पैटर्न" },
  siteActivity: { en: "Site × activity", hi: "साइट × गतिविधि" },
  activityBarrier: { en: "Activity × failed barrier", hi: "गतिविधि × विफल अवरोध" },
  demoDisclosure: { en: "Synthetic OIL-style demo data", hi: "कृत्रिम OIL-शैली डेमो डेटा" },
  queueHelp: {
    en: "Why some reports need manual review",
    hi: "कुछ रिपोर्टों को मानवीय समीक्षा क्यों चाहिए",
  },
  emptyQueue: {
    en: "No reports yet. Classify a report or import a CSV to begin.",
    hi: "अभी कोई रिपोर्ट नहीं। शुरू करने के लिए रिपोर्ट वर्गीकृत करें या CSV आयात करें।",
  },
  skipContent: { en: "Skip to content", hi: "मुख्य सामग्री पर जाएँ" },
  hseOperations: { en: "HSE operations", hi: "HSE संचालन" },
  operationalOverview: { en: "Operational overview", hi: "संचालन अवलोकन" },
  patternSiteBlurb: {
    en: "Recurring activity and site combinations that may warrant a planned inspection.",
    hi: "बार-बार दिखने वाले गतिविधि और साइट संयोजन जिनके लिए नियोजित निरीक्षण आवश्यक हो सकता है।",
  },
  patternBarrierBlurb: {
    en: "Repeated activity and failed-barrier combinations that show where safeguards break down.",
    hi: "दोहराते गतिविधि और विफल-अवरोध संयोजन जो बताते हैं कि सुरक्षा उपाय कहाँ टूट रहे हैं।",
  },
  noPatterns: { en: "No patterns yet. Import more reports to begin.", hi: "अभी कोई पैटर्न नहीं। शुरू करने के लिए और रिपोर्ट आयात करें।" },
  reportsReviewed: { en: "reports reviewed", hi: "रिपोर्ट समीक्षित" },
  flaggedPer100: { en: "flagged per 100", hi: "प्रति 100 चिह्नित" },
  statisticalDetail: { en: "Statistical detail", hi: "सांख्यिकीय विवरण" },
  showTop10: { en: "Show top 10 only", hi: "केवल शीर्ष 10 दिखाएँ" },
  showAllPatterns: { en: "Show all patterns", hi: "सभी पैटर्न दिखाएँ" },
  showTop20: { en: "Show top 20 only", hi: "केवल शीर्ष 20 दिखाएँ" },
  showAllLocations: { en: "Show all locations", hi: "सभी स्थान दिखाएँ" },
  noDecisions: { en: "No decisions recorded yet", hi: "अभी कोई निर्णय दर्ज नहीं" },
  noDecisionsBody: {
    en: "Review a report in Triage and record an outcome. It will appear here as part of the audit trail.",
    hi: "ट्रायाज में रिपोर्ट की समीक्षा कर परिणाम दर्ज करें। वह यहाँ ऑडिट रिकॉर्ड में दिखाई देगा।",
  },
  queueFilters: { en: "Queue filters", hi: "कतार फ़िल्टर" },
  pastedNow: { en: "Pasted just now in this session", hi: "इस सत्र में अभी पेस्ट किया गया" },
  possibleDuplicate: { en: "Possible duplicate", hi: "संभावित डुप्लिकेट" },
  gateShort: { en: "Review", hi: "समीक्षा" },
  wellControlTag: { en: "Well-control / barrier tag", hi: "वेल-कंट्रोल / अवरोध टैग" },
  loadingExplanation: { en: "Loading explanation", hi: "व्याख्या लोड हो रही है" },
  explanationUnavailable: {
    en: "Explanation is unavailable while the service is offline.",
    hi: "सेवा ऑफ़लाइन होने पर व्याख्या उपलब्ध नहीं है।",
  },
  cached: { en: "cached", hi: "संग्रहीत" },
  rank: { en: "Rank", hi: "रैंक" },
  site: { en: "Site", hi: "साइट" },
  reports: { en: "Reports", hi: "रिपोर्ट" },
  flagged: { en: "Flagged", hi: "चिह्नित" },
  flagRate: { en: "Flag rate", hi: "चिह्नित दर" },
  movement: { en: "Movement", hi: "बदलाव" },
  climbedToFirst: { en: "just climbed to #1", hi: "अभी #1 पर पहुँचा" },
  // ---- shell (routes.tsx / App.tsx) ----
  tabIngest: { en: "Add Reports", hi: "रिपोर्ट जोड़ें" },
  mainNav: { en: "Main navigation", hi: "मुख्य नेविगेशन" },
  openMenu: { en: "Open menu", hi: "मेनू खोलें" },
  menuTitle: { en: "Menu", hi: "मेनू" },
  themeLabel: { en: "Color theme", hi: "रंग थीम" },
  themeLight: { en: "Light", hi: "लाइट" },
  themeDark: { en: "Dark", hi: "डार्क" },
  themeSystem: { en: "System", hi: "सिस्टम" },
  langLabel: { en: "Language", hi: "भाषा" },
  viewLimitations: { en: "Data & limitations", hi: "डेटा और सीमाएँ" },
  footerDisclosure: {
    en: "Synthetic demo data, not OIL incident records.",
    hi: "कृत्रिम डेमो डेटा, OIL की वास्तविक घटना रिपोर्ट नहीं।",
  },
  errorTitle: { en: "Could not load this data", hi: "यह डेटा लोड नहीं हो सका" },
  errorBody: {
    en: "This page could not be loaded. Reload the page to try again.",
    hi: "यह पेज लोड नहीं हो सका। पुनः प्रयास के लिए पेज फिर से लोड करें।",
  },
  retry: { en: "Retry", hi: "पुनः प्रयास" },
  tryAgain: { en: "Try Again", hi: "पुनः प्रयास" },
  clearDates: { en: "Clear dates", hi: "तारीखें हटाएँ" },
  close: { en: "Close", hi: "बंद करें" },
  reloadPage: { en: "Reload page", hi: "पेज पुनः लोड करें" },
  routePending: { en: "This surface is being rebuilt", hi: "यह सतह फिर से बनाई जा रही है" },
  routePendingBody: {
    en: "This screen has not landed in this build yet. No placeholder data is shown.",
    hi: "यह स्क्रीन इस बिल्ड में अभी नहीं आई है। कोई प्लेसहोल्डर डेटा नहीं दिखाया जाता।",
  },
  routeNotFound: { en: "Page not found", hi: "पेज नहीं मिला" },
  routeNotFoundBody: {
    en: "That address is not part of this dashboard.",
    hi: "वह पता इस डैशबोर्ड का हिस्सा नहीं है।",
  },
  // ---- decisions / rationale (Workstream C: audit trail) ----
  rationale: { en: "Rationale", hi: "कारण" },
  rationalePlaceholder: {
    en: "Why this decision? Recorded in the audit trail.",
    hi: "यह निर्णय क्यों? ऑडिट रिकॉर्ड में दर्ज होता है।",
  },
  rationaleMissing: { en: "No rationale recorded", hi: "कोई कारण दर्ज नहीं" },
  // ---- ingest job progress (INGEST workstream) ----
  statusQueued: { en: "Queued", hi: "कतार में" },
  statusRunning: { en: "Running", hi: "चल रहा है" },
  statusDone: { en: "Done", hi: "पूर्ण" },
  statusFailed: { en: "Failed", hi: "विफल" },
  statusCancelled: { en: "Cancelled", hi: "रद्द" },
  // ---- verdict stability (Workstream A3 self-consistency) ----
  stabilityStable: { en: "Stable verdict", hi: "स्थिर निर्णय" },
  stabilityUnstable: {
    en: "Unstable wording — routed to review",
    hi: "अस्थिर शब्दावली — समीक्षा में भेजा गया",
  },
  // ---- review-priority band words (server-owned operating point) ----
  bandHigh: { en: "HIGH", hi: "उच्च" },
  bandModerate: { en: "MODERATE", hi: "मध्यम" },
  bandLow: { en: "LOW", hi: "कम" },
  bandClear: { en: "CLEAR", hi: "स्पष्ट" },
  bandReview: { en: "REVIEW", hi: "समीक्षा" },
} as const;

/* ---- Gate copy — the single source for the whole gate system ----
 * Merged here from components/gray-state-card.tsx (legacy 10 gates, EN/HI
 * text kept verbatim) and extended with the barrier-failure gate family
 * (Workstream A2). UI components render gate names only through
 * gateCopyFor() — never via an exhaustive Record<GateKind, …> lookup, because
 * the wire field is a free string and unknown names must
 * degrade to the honest fallback, not crash. */

export interface GateCopyEntry {
  name: { en: string; hi: string };
  sentence: { en: string; hi: string };
}

export const GATE_COPY: Record<string, GateCopyEntry> = {
  min_length: {
    name: { en: "Very short report", hi: "बहुत छोटी रिपोर्ट" },
    sentence: {
      en: "Very short text with no recognized safety short code — not enough signal to score reliably. Routed to review, never auto-cleared.",
      hi: "विश्वसनीय स्कोर के लिए पर्याप्त जानकारी नहीं है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  negation: {
    name: { en: "Negation detected", hi: "नकारात्मक वाक्य मिला" },
    sentence: {
      en: "\u2018No injury\u2019 phrasing detected — the model may be reading outcome words, not mechanism. Routed to review, never auto-cleared.",
      hi: "मॉडल घटना के कारण के बजाय परिणाम के शब्द पढ़ सकता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  language: {
    name: { en: "Language not currently scored", hi: "यह भाषा अभी स्कोर नहीं की जाती" },
    sentence: {
      en: "Language beyond current scoring support — the original text is preserved and routed to review, never silently mis-scored.",
      hi: "मूल पाठ सुरक्षित रखा गया है और गलत स्कोर देने के बजाय मानवीय समीक्षा में भेजा गया है।",
    },
  },
  confidence: {
    name: { en: "Uncertain score", hi: "अनिश्चित स्कोर" },
    sentence: {
      en: "The score sits in the uncertain band — not enough signal to rank confidently. Routed to review, never auto-cleared.",
      hi: "विश्वसनीय प्राथमिकता तय करने के लिए संकेत पर्याप्त नहीं है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  drill: {
    name: { en: "Report mentions a drill or test", hi: "रिपोर्ट में ड्रिल या परीक्षण का उल्लेख है" },
    sentence: {
      en: "Drill or exercise language detected — a rehearsal is not a precursor. Routed to review, never auto-cleared.",
      hi: "अभ्यास वास्तविक घटना नहीं है। रिपोर्ट को मानवीय समीक्षा में भेजा गया है।",
    },
  },
  near_dup: {
    name: { en: "Possible duplicate of a training record", hi: "प्रशिक्षण रिकॉर्ड का संभावित डुप्लिकेट" },
    sentence: {
      en: "Matches a training record — memory, not generalization. Shown as a banner on the triage card.",
      hi: "यह प्रशिक्षण रिकॉर्ड से मेल खाता है — सामान्यीकरण नहीं, स्मृति।",
    },
  },
  long_input: {
    name: { en: "Long report, scored in sections", hi: "लंबी रिपोर्ट, खंडों में स्कोर" },
    sentence: {
      en: "Over 120 words — scored section by section, since very long reports are rare in training. Marked as \u2018scored in sections\u2019 on the card.",
      hi: "लंबी रिपोर्ट को अधिक विश्वसनीय परिणाम के लिए खंडों में स्कोर किया गया है।",
    },
  },
  well_control_watch: {
    name: { en: "Possible well-control concern", hi: "संभावित वेल-कंट्रोल चिंता" },
    sentence: {
      en: "Well-control/barrier language detected, but the triage score is below the flag threshold — a rare, high-consequence domain where automated screening defers. Routed to human review, never auto-cleared.",
      hi: "वेल-कंट्रोल या अवरोध भाषा मिली है। दुर्लभ और गंभीर जोखिम के कारण इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  chunked_low_score: {
    name: { en: "Long report with uncertain score", hi: "अनिश्चित स्कोर वाली लंबी रिपोर्ट" },
    sentence: {
      en: "A long report scored in sections landed in the uncertain band — section scoring can discount mid-text hazards. Routed to human review, never auto-cleared.",
      hi: "खंडों में स्कोर की गई रिपोर्ट अनिश्चित श्रेणी में है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  severity_watch: {
    name: { en: "Serious-event language, low score", hi: "गंभीर घटना की भाषा, कम स्कोर" },
    sentence: {
      en: "The report mentions an injury or high-energy event, but the score is low — the model may have missed it. Routed to human review, never auto-cleared.",
      hi: "रिपोर्ट में चोट या उच्च-ऊर्जा घटना का उल्लेख है, पर स्कोर कम है — मॉडल इसे चूक सकता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  verdict_stability: {
    name: { en: "Verdict changes with wording", hi: "शब्द बदलने पर निर्णय बदलता है" },
    sentence: {
      en: "Fewer than 75% of the scored surface variants agree with the ensemble verdict — the result is sensitive to rephrasing. Routed to human review; the score and operating point are unchanged.",
      hi: "स्कोर किए गए वाक्य-विन्यासों में 75% से कम, संयुक्त निर्णय से सहमत हैं — परिणाम दोबारा लिखने पर बदल सकता है। स्कोर और ऑपरेटिंग पॉइंट बदले बिना मानवीय समीक्षा में भेजा गया है।",
    },
  },
  // Barrier-failure gate family (Workstream A2) — fire on explicit ABSENCE of
  // control language; a bare mention is advisory, "LOTO applied and verified"
  // must not fire. Copy mirrors the semantic, not the regex.
  energy_isolation_absent: {
    name: { en: "Energy isolation not verified", hi: "ऊर्जा अवरोधन सत्यापित नहीं" },
    sentence: {
      en: "No lockout/tagout or verified isolation of energised equipment is described — the energy-isolation barrier appears absent. Routed to human review, never auto-cleared.",
      hi: "लॉकआउट/टैगआउट या ऊर्जायुक्त उपकरण का सत्यापित अवरोधन वर्णित नहीं है — ऊर्जा-अवरोधन अवरोध अनुपस्थित प्रतीत होता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  gas_test_absent: {
    name: { en: "Gas test not performed", hi: "गैस टेस्ट नहीं हुआ" },
    sentence: {
      en: "No gas test or atmospheric reading before entry into a confined or suspect atmosphere — the gas-testing barrier appears absent. Routed to human review, never auto-cleared.",
      hi: "संपीड़ित या संदिग्ध वातावरण में प्रवेश से पहले कोई गैस परीक्षण या वायुमंडलीय रीडिंग वर्णित नहीं है — गैस-परीक्षण अवरोध अनुपस्थित प्रतीत होता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  permit_absent: {
    name: { en: "Permit to work not raised", hi: "परमिट जारी नहीं हुआ" },
    sentence: {
      en: "Work proceeds with no permit to work described — the work-authorisation barrier appears absent. Routed to human review, never auto-cleared.",
      hi: "कार्य बिना परमिट के वर्णित है — कार्य-अधिकृति अवरोध अनुपस्थित प्रतीत होता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  fire_watch_absent: {
    name: { en: "Fire watch absent", hi: "फायर वॉच अनुपस्थित" },
    sentence: {
      en: "Hot-work report with no fire watch posted, or the watch left — the fire-watch barrier appears absent. Routed to human review, never auto-cleared.",
      hi: "हॉट-वर्क रिपोर्ट में कोई फायर वॉच तैनात नहीं है, या वह छोड़ गया — फायर-वॉच अवरोध अनुपस्थित प्रतीत होता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  standby_absent: {
    name: { en: "Standby man not posted", hi: "स्टैंडबाय व्यक्ति तैनात नहीं" },
    sentence: {
      en: "Confined-space work with no standby man or attendant described — the standby barrier appears absent. Routed to human review, never auto-cleared.",
      hi: "कॉन्फाइंड-स्पेस कार्य में कोई स्टैंडबाय व्यक्ति या पर्यवेक्षक वर्णित नहीं है — स्टैंडबाय अवरोध अनुपस्थित प्रतीत होता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  atmosphere_unmonitored: {
    name: { en: "Atmosphere unmonitored", hi: "वातावरण पर निगरानी नहीं" },
    sentence: {
      en: "Purging or entry in progress with no continuous atmospheric monitoring described — the monitoring barrier appears absent. Routed to human review, never auto-cleared.",
      hi: "पर्जिंग या प्रवेश जारी है, पर निरंतर वायुमंडलीय निगरानी वर्णित नहीं है — निगरानी अवरोध अनुपस्थित प्रतीत होता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
  fall_protection_absent: {
    name: { en: "Fall protection absent", hi: "गिरने से बचाव अनुपस्थित" },
    sentence: {
      en: "Work at height is described without fall-protection anchorage or a harness — the fall-protection barrier appears absent. Routed to human review, never auto-cleared.",
      hi: "ऊँचाई पर काम का वर्णन है, पर गिरने से बचाव का एंकर या हार्नेस नहीं बताया गया — गिरने से बचाव का अवरोध अनुपस्थित प्रतीत होता है। इसे मानवीय समीक्षा में भेजा गया है।",
    },
  },
};

/** Legend/ordering list: general gates, then the barrier-failure family. */
export const KNOWN_GATE_NAMES: string[] = [
  "min_length",
  "negation",
  "language",
  "confidence",
  "drill",
  "near_dup",
  "long_input",
  "well_control_watch",
  "chunked_low_score",
  "severity_watch",
  "verdict_stability",
  "energy_isolation_absent",
  "gas_test_absent",
  "permit_absent",
  "fire_watch_absent",
  "standby_absent",
  "atmosphere_unmonitored",
  "fall_protection_absent",
];

/** Gate display copy for ANY wire name — falls back to the raw name + a
 *  generic honest sentence when the gate is unknown to this build. */
export function gateCopyFor(
  lang: Lang,
  name: string,
): { name: string; sentence: string; known: boolean } {
  const entry = GATE_COPY[name];
  if (!entry) {
    return {
      name,
      sentence:
        lang === "hi"
          ? "इस रिपोर्ट को गेट सिस्टम ने मानवीय समीक्षा के लिए भेजा है।"
          : "The gate system routed this report to human review.",
      known: false,
    };
  }
  return { name: entry.name[lang], sentence: entry.sentence[lang], known: true };
}

export type StringKey = keyof typeof STRINGS;

export function t(lang: Lang, key: StringKey): string {
  return STRINGS[key][lang];
}
