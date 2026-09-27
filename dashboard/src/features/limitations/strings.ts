/* Settings-feature strings (EN/हिं) — same idiom as @/lib/phrasebook.ts.
 * Kept in-slice because lib/** is SHELL-owned; SHELL may hoist these keys
 * into the global phrasebook later without changing call sites. Source
 * reports and gate identifiers stay verbatim; only UI chrome is translated. */
import type { Lang } from "@/lib/phrasebook";

const S = {
  /* page chrome */
  pageTitle: {
    en: "Model ops, runtime & limitations",
    hi: "मॉडल ऑप्स, रनटाइम और सीमाएँ",
  },
  pageIntro: {
    en: "Model provenance, evaluation results and limits on use.",
    hi: "मॉडल का स्रोत, मूल्यांकन परिणाम और उपयोग की सीमाएँ।",
  },
  jumpToLimitations: { en: "Jump to limitations", hi: "सीमाओं तक जाएँ" },

  /* shared states (no fabricated fallbacks) */
  loadingData: { en: "Loading live data…", hi: "लाइव डेटा लोड हो रहा है…" },
  offlineNote: {
    en: "Live metrics unavailable. Model provenance and saved evaluation results remain available.",
    hi: "लाइव मापदंड उपलब्ध नहीं हैं। मॉडल का स्रोत और सहेजे मूल्यांकन परिणाम उपलब्ध हैं।",
  },
  retry: { en: "Retry", hi: "पुनः प्रयास" },
  notAvailableOffline: { en: "— unavailable offline", hi: "— ऑफ़लाइन उपलब्ध नहीं" },

  /* MODEL OPS */
  panelModelOps: { en: "Model ops", hi: "मॉडल ऑप्स" },
  shippedArtifact: { en: "Shipped artifact", hi: "शिप किया आर्टिफैक्ट" },
  loadedAtRuntime: { en: "Loaded at runtime", hi: "रनटाइम पर लोड" },
  classifierClass: { en: "Classifier class", hi: "वर्गीकरण इंजन" },
  classifierReal: { en: "real ONNX inference", hi: "वास्तविक ONNX इनफ़रेंस" },
  classifierMock: {
    en: "mock classifier — scores are scripted, not model output",
    hi: "मॉक वर्गीकरणकर्ता — स्कोर स्क्रिप्टेड हैं, मॉडल आउटपुट नहीं",
  },
  backboneLine: {
    en: "Backbone",
    hi: "बैकबोन",
  },
  trainedLine: { en: "Trained", hi: "प्रशिक्षण" },
  trainedValue: { en: "3 epochs · 2026-09-08 · Kaggle 2×T4", hi: "3 एपॉक · 08-09-2026 · Kaggle 2×T4" },

  opPointTitle: {
    en: "Tuned operating point (flag threshold)",
    hi: "ट्यून किया ऑपरेटिंग पॉइंट (फ़्लैग सीमा)",
  },
  opPointServed: { en: "Served flag threshold (calibrated scale)", hi: "सर्व की गई फ़्लैग सीमा (कैलिब्रेटेड स्केल)" },
  opPointRaw: { en: "Raw-sigmoid threshold", hi: "रॉ-सिग्मॉइड सीमा" },
  opPointTemp: { en: "Temperature T", hi: "टेम्परेचर T" },
  opPointSelection: { en: "Selection rule", hi: "चयन नियम" },
  opPointSelectionValue: {
    en: "max recall subject to precision ≥ 0.80",
    hi: "प्रेसिज़न ≥ 0.80 रखते हुए अधिकतम रिकॉल",
  },
  opPointTunedOn: { en: "Tuned on", hi: "ट्यून किया गया" },
  opPointTunedOnValue: {
    en: "derived-label test split (temporal holdout, gold-independent) · n=17,731 · prevalence 64.2% · 2026-09-08",
    hi: "व्युत्पन्न-लेबल टेस्ट स्प्लिट (टेम्पोरल होल्डआउट, गोल्ड-स्वतंत्र) · n=17,731 · प्रचलन 64.2% · 08-09-2026",
  },
  opPointAtPoint: { en: "At this point (test split)", hi: "इस पॉइंट पर (टेस्ट स्प्लिट)" },
  opPointFlagRate: { en: "flag rate", hi: "फ़्लैग दर" },
  opPointProvenance: { en: "evidence", hi: "साक्ष्य" },
  grayBandTitle: { en: "Gray review band", hi: "ग्रे समीक्षा बैंड" },
  grayBandValue: {
    en: "scores inside this band route to human review, never auto-cleared",
    hi: "इस बैंड के स्कोर मानव समीक्षा हेतु जाते हैं, कभी स्वतः साफ़ नहीं",
  },

  calibrationTitle: { en: "Calibration status", hi: "कैलिब्रेशन स्थिति" },
  calibrationLive: { en: "LIVE METRIC", hi: "लाइव मेट्रिक" },
  calibrationMeasuredOnce: { en: "MEASURED ONCE", hi: "एक बार मापा गया" },
  calibrationRawLabel: { en: "Raw (measured once)", hi: "रॉ (एक बार मापा गया)" },
  calibrationCalibratedLabel: { en: "Temperature-scaled", hi: "टेम्परेचर-स्केल्ड" },
  calibrationNote: {
    en: "Temperature T=1.648 was fit on validation. This ECE is mediocre, not a pass: temperature scaling did not make calibration good. These held-out metrics use derived labels, not OIL prevalence.",
    hi: "वैलिडेशन डेटा पर टेम्परेचर T=1.648 फिट किया गया। यह ECE औसत दर्जे का है, पास नहीं: टेम्परेचर-स्केलिंग से कैलिब्रेशन अच्छा नहीं हुआ। ये अलग रखे मेट्रिक्स व्युत्पन्न लेबल पर हैं, OIL प्रचलन पर नहीं।",
  },

  gatesTitle: { en: "Sentinel gates — live trigger counts", hi: "सेंटिनल गेट — लाइव ट्रिगर गिनती" },
  gateColGate: { en: "Gate", hi: "गेट" },
  gateColCount: { en: "Triggers", hi: "ट्रिगर" },
  gateColAction: { en: "Action", hi: "क्रिया" },
  gateBadgeLabel: { en: "badge — annotate only", hi: "बैज — केवल सूचना" },
  gateGrayLabel: { en: "gray — routes to review", hi: "ग्रे — समीक्षा हेतु" },
  gatesBadgeSummary: {
    en: "{n} of {total} triggers ({pct}%) are badge annotations — mostly near-duplicate banners.",
    hi: "{total} में से {n} ट्रिगर ({pct}%) बैज हैं — अधिकतर नियर-डुप्लिकेट बैनर।",
  },
  gatesGraySummary: {
    en: "{n} ({pct}%) actually route reports to human review.",
    hi: "{n} ({pct}%) वास्तव में रिपोर्ट को मानव समीक्षा में भेजते हैं।",
  },
  gatesDrown: {
    en: "Badge volume buries the gray cases — read the gray rows first.",
    hi: "बैज की संख्या ग्रे मामलों को दबा देती है — पहले ग्रे पंक्तियाँ पढ़ें।",
  },
  gatesEmpty: {
    en: "Gate counts come from the live API — unavailable offline.",
    hi: "गेट गिनती लाइव API से आती है — ऑफ़लाइन उपलब्ध नहीं।",
  },
  gMinLength: { en: "Minimum length", hi: "न्यूनतम लंबाई" },
  gNegation: { en: "Negated outcome", hi: "निषेधित परिणाम" },
  gLanguage: { en: "Language", hi: "भाषा" },
  gConfidence: { en: "Gray-band confidence", hi: "ग्रे-बैंड विश्वास" },
  gDrill: { en: "Drill / simulation", hi: "ड्रिल / अभ्यास" },
  gNearDup: { en: "Near-duplicate of training row", hi: "प्रशिक्षण पंक्ति का नियर-डुप्लिकेट" },
  gLongInput: { en: "Long input (chunked)", hi: "लंबा इनपुट (खंडित)" },
  gWellControl: { en: "Well-control watch", hi: "वेल-कंट्रोल वॉच" },
  gChunkedLow: { en: "Chunked low score", hi: "खंडित निम्न स्कोर" },
  gSeverity: { en: "Severity watch", hi: "गंभीरता वॉच" },

  corpusTitle: { en: "Corpus provenance", hi: "कॉर्पस का स्रोत" },
  corpusSourcesLabel: { en: "Sources", hi: "स्रोत" },
  corpusOsha: {
    en: "OSHA Severe Injury Reports — 105,996 narratives (US post-injury proxy)",
    hi: "OSHA गंभीर-चोट रिपोर्ट — 105,996 विवरण (अमेरिकी दुर्घटना-पश्चात प्रॉक्सी)",
  },
  corpusAsrs: {
    en: "NASA ASRS aviation reports — negatives only, outcome-masked",
    hi: "NASA ASRS एविएशन रिपोर्ट — केवल नकारात्मक, परिणाम-मास्क्ड",
  },
  corpusSynthetic: {
    en: "Synthetic OIL-register rows — QA-gated, train split only",
    hi: "संश्लिष्ट OIL-शैली पंक्तियाँ — QA-गेटेड, केवल ट्रेन स्प्लिट",
  },
  corpusSplit: {
    en: "Temporal split (train ≤ 2023-12-31 · test 2024-01-01 → 2025-11-30), employer-grouped validation, 8-gram boundary screen; all narratives outcome-masked at training time.",
    hi: "टेम्पोरल स्प्लिट (train ≤ 2023-12-31 · test 2024-01-01 → 2025-11-30), नियोक्ता-समूहित वैलिडेशन, 8-ग्राम बाउंड्री स्क्रीन; सभी विवरण प्रशिक्षण के समय परिणाम-मास्क्ड।",
  },
  corpusPos: {
    en: "63.5% of corpus rows are positive — severe-injury-only inclusion, not OIL prevalence",
    hi: "कॉर्पस की 63.5% पंक्तियाँ positive — गंभीर-चोट-मात्र समावेशन, OIL प्रचलन नहीं",
  },
  demoSeed: {
    en: "The demo DB is seeded from this same corpus (top-1 near-dup cosine 0.99998): it scores itself. The live flag rate is a seeding artifact, not a field measurement.",
    hi: "डेमो DB इसी कॉर्पस से सीड किया गया है (टॉप-1 नियर-डुप कोसाइन 0.99998): यह स्वयं को स्कोर करता है। लाइव फ़्लैग दर सीडिंग-कला है, क्षेत्र-माप नहीं।",
  },

  goldTitle: {
    en: "Gold evaluation — n=500, 4 labelers, consensus + adjudication",
    hi: "गोल्ड मूल्यांकन — n=500, 4 लेबलर्स, सर्वसम्मति + अधिवाचन",
  },
  goldHeadlineLabel: { en: "Headline — real pooled (n=318)", hi: "मुख्य नतीजा — वास्तविक समूहित (n=318)" },
  goldHeadlineValue: {
    en: "precision 0.976 · recall 0.836 — measured at 89.9% gold prevalence",
    hi: "प्रेसिज़न 0.976 · रिकॉल 0.836 — 89.9% गोल्ड प्रचलन पर मापा",
  },
  goldAsrsLabel: { en: "ASRS stratum (n=37)", hi: "ASRS स्ट्रैटम (n=37)" },
  goldAsrsValue: { en: "recall 0.00", hi: "रिकॉल 0.00" },
  goldSyntheticLabel: { en: "Synthetic stratum (n=89)", hi: "संश्लिष्ट स्ट्रैटम (n=89)" },
  goldSyntheticValue: {
    en: "precision 0.347 · recall 0.944 (prevalence 20.2%)",
    hi: "प्रेसिज़न 0.347 · रिकॉल 0.944 (प्रचलन 20.2%)",
  },
  exportGateLabel: { en: "INT8 export gate", hi: "INT8 एक्सपोर्ट गेट" },
  exportGateChip: { en: "Validation gate failed", hi: "सत्यापन जाँच विफल" },
  exportGateNote: {
    en: "INT8 vs FP32: decision agreement 99.3%, ΔAUC 0.1305, recall drop at the operating point 0.0. The deployed INT8 model failed the export validation gate; its review threshold was tuned on the INT8 chain.",
    hi: "INT8 बनाम FP32: निर्णय-सहमति 99.3%, ΔAUC 0.1305, ऑपरेटिंग पॉइंट पर रिकॉल में गिरावट 0.0। तैनात INT8 मॉडल एक्सपोर्ट सत्यापन में विफल हुआ; उसकी समीक्षा सीमा INT8 शृंखला पर तय की गई।",
  },

  /* RUNTIME */
  panelRuntime: { en: "Runtime", hi: "रनटाइम" },
  rtOnline: { en: "online — local API reachable", hi: "ऑनलाइन — लोकल API उपलब्ध" },
  rtOffline: { en: "offline — API unreachable from this dashboard", hi: "ऑफ़लाइन — API इस डैशबोर्ड से उपलब्ध नहीं" },
  rtStackTitle: { en: "Execution surface", hi: "निष्पादन प्लेटफ़ॉर्म" },
  rtStack: {
    en: "100% local: uvicorn + SQLite + ONNX Runtime (CPU, int8). No torch, no docker, no network calls at inference.",
    hi: "100% लोकल: uvicorn + SQLite + ONNX Runtime (CPU, int8)। torch नहीं, docker नहीं, इनफ़रेंस में कोई नेटवर्क कॉल नहीं।",
  },
  rtReports: { en: "Reports in database", hi: "डेटाबेस में रिपोर्ट" },
  rtOverrides: { en: "Recorded human decisions", hi: "दर्ज मानवीय निर्णय" },
  rtFlagRate: { en: "Flag rate (this database)", hi: "फ़्लैग दर (यह डेटाबेस)" },
  rtMeanScore: { en: "Mean triage score", hi: "औसत ट्रायाज स्कोर" },
  rtThroughputTitle: { en: "Measured ingest throughput", hi: "मापी गई इनजेस्ट गति" },
  rtThroughputValue: { en: "7.3 rows/s", hi: "7.3 पंक्तियाँ/सेकंड" },
  rtThroughputNote: {
    en: "500-row demo batch: 68.9 s end-to-end on this stack (2026-09-25). Earlier docs claimed 45.6 rows/s — that number was never measured and has been withdrawn.",
    hi: "500-पंक्ति डेमो बैच: इस स्टैक पर 68.9 s (25-09-2026)। पहले के दस्तावेज़ों में 45.6 पंक्तियाँ/सेकंड लिखा था — वह कभी मापा नहीं गया और वापस ले लिया गया है।",
  },
  rtOllamaTitle: { en: "Explanation LLM (Ollama · optional)", hi: "व्याख्या LLM (Ollama · वैकल्पिक)" },
  rtOllamaChip: { en: "optional — never load-bearing", hi: "वैकल्पिक — कभी आधारभूत नहीं" },
  rtOllamaNote: {
    en: "The deterministic template always ships — it is the product. This dashboard pins the LLM off on its live-classify path (?llm=0) and never waits on it; the redesign removes it as a server default (SIF_EXPLAIN_LLM=0). Reword-cache hit rate on the demo DB: 0/63 (measured).",
    hi: "नियतात्मक टेम्पलेट हमेशा उपलब्ध रहता है — वही उत्पाद है। यह डैशबोर्ड अपने लाइव-क्लासिफ़ाई पथ (?llm=0) पर LLM बंद रखता है और कभी उसकी प्रतीक्षा नहीं करता; पुनर्डिज़ाइन इसे सर्वर डिफ़ॉल्ट से हटाता है (SIF_EXPLAIN_LLM=0)। डेमो DB पर रीवर्ड-कैश हिट दर: 0/63 (मापा गया)।",
  },
  rtOllamaNotProbed: {
    en: "Availability is not probed from the UI — no status endpoint exists.",
    hi: "UI से इसकी उपलब्धता जाँची नहीं जाती — कोई स्टेटस एंडपॉइंट नहीं है।",
  },

  /* LIMITATIONS */
  panelLimitations: { en: "Model limitations", hi: "मॉडल की सीमाएँ" },
  limitationsIntro: {
    en: "Use assessments to support human review, not to clear work as safe. Safeguards reduce these risks but do not eliminate them.",
    hi: "आकलन मानव समीक्षा में सहायक हैं, काम को सुरक्षित घोषित करने का आधार नहीं। सुरक्षा उपाय इन जोखिमों को घटाते हैं, समाप्त नहीं करते।",
  },
  evidenceLabel: { en: "evidence", hi: "साक्ष्य" },

  lim1Title: { en: "US post-injury training proxy", hi: "अमेरिकी दुर्घटना-पश्चात प्रशिक्षण प्रॉक्सी" },
  lim1Body: {
    en: "The training distribution is OSHA severe-injury narratives plus synthetic text — not OIL’s UA/UC or near-miss register. The model reads OIL reports off-distribution.",
    hi: "प्रशिक्षण डेटा OSHA गंभीर-चोट विवरण और संश्लिष्ट पाठ पर आधारित है — OIL की UA/UC या नियर-मिस शैली पर नहीं। मॉडल OIL की रिपोर्टें ऑफ़-डिस्ट्रिब्यूशन पढ़ता है।",
  },
  lim1Evidence: { en: "data_pipeline/build_corpus.py · docs/redesign-plan.md §5.1", hi: "data_pipeline/build_corpus.py · docs/redesign-plan.md §5.1" },
  lim2Title: { en: "Out-of-distribution collapse: ASRS recall 0.00", hi: "ऑफ़-डिस्ट्रिब्यूशन पतन: ASRS रिकॉल 0.00" },
  lim2Body: {
    en: "On the gold set, the NASA ASRS stratum (n=37) scored 0.00 recall — all 19 true positives missed. This is what off-distribution looks like for this model.",
    hi: "गोल्ड सेट पर NASA ASRS स्ट्रैटम (n=37) का रिकॉल 0.00 रहा — सभी 19 सही-positive छूट गए। इस मॉडल के लिए ऑफ़-डिस्ट्रिब्यूशन यही दिखता है।",
  },
  lim2Evidence: { en: "artifacts/gold/gold_metrics_final.json → strata.asrs", hi: "artifacts/gold/gold_metrics_final.json → strata.asrs" },
  lim3Title: { en: "Procedural barrier failures are under-detected", hi: "प्रक्रियात्मक अवरोध-चूक कम पकड़ी जाती हैं" },
  lim3Body: {
    en: "No gas test before tank entry, LOTO omitted, no permit, no fire watch — the model score alone misses these (probes: 0.318, 0.280, 0.126 — all below threshold). They are mitigated only by the deterministic barrier-failure gates, and only when the absence is stated explicitly.",
    hi: "टैंक-प्रवेश से पहले गैस टेस्ट नहीं, LOTO छूटा, परमिट नहीं, फायर वॉच नहीं — मॉडल स्कोर अकेले इन्हें चूकता है (प्रोब: 0.318, 0.280, 0.126 — सभी सीमा से नीचे)। इनका शमन केवल नियतात्मक अवरोध-चूक गेट से होता है, और वह भी तब जब अनुपस्थिति स्पष्ट रूप से लिखी हो।",
  },
  lim3Evidence: {
    en: "docs/discovery/60-orchestrator-novel-probe.md (results 2, 5) · implementation-plan.md §A2",
    hi: "docs/discovery/60-orchestrator-novel-probe.md (results 2, 5) · implementation-plan.md §A2",
  },
  lim4Title: { en: "Scores are unstable under paraphrase", hi: "पैराफ्रेज़ पर स्कोर अस्थिर हैं" },
  lim4Body: {
    en: "Meaning-preserving rewrites have flipped verdicts (one confined-space scenario: 0.026 → 0.861, sd 0.31). Self-consistency averaging reduces the spread (sd 0.308 → 0.076) — that fixes reliability, NOT validity: the stabilised consensus for procedural cases is still unflagged.",
    hi: "वही अर्थ रखते पुनर्लेखन से निर्णय पलट गए (एक कन्फ़ाइंड-स्पेस परिदृश्य: 0.026 → 0.861, sd 0.31)। सेल्फ-कंसिस्टेंसी औसत फैलाव घटाता है (sd 0.308 → 0.076) — इससे विश्वसनीयता (reliability) सुधरती है, वैधता (validity) नहीं: प्रक्रियात्मक मामलों का स्थिर सर्वसम्मत उत्तर अब भी अनफ़्लैग्ड है।",
  },
  lim4Evidence: {
    en: "docs/discovery/60-orchestrator-novel-probe.md (results 3, 6) · implementation-plan.md §A3",
    hi: "docs/discovery/60-orchestrator-novel-probe.md (results 3, 6) · implementation-plan.md §A3",
  },
  lim5Title: { en: "The 71% flag rate is a demo artifact", hi: "71% फ़्लैग दर डेमो-कला है" },
  lim5Body: {
    en: "This database is seeded from the training corpus, so it scores itself (top-1 near-dup cosine 0.99998). The live flag rate (0.7095) is not a field measurement and will not transfer to OIL’s reporting mix.",
    hi: "यह डेटाबेस प्रशिक्षण कॉर्पस से सीड किया गया है, इसलिए यह स्वयं को स्कोर करता है (टॉप-1 नियर-डुप कोसाइन 0.99998)। लाइव फ़्लैग दर (0.7095) क्षेत्र-माप नहीं है और OIL के वास्तविक मिश्रण पर लागू नहीं होगी।",
  },
  lim5Evidence: {
    en: "live /api/metrics/summary flag_rate 0.7095 (2026-09-25) · docs/redesign-plan.md §5.1",
    hi: "live /api/metrics/summary flag_rate 0.7095 (2026-09-25) · docs/redesign-plan.md §5.1",
  },
  lim6Title: { en: "No deployment-prevalence precision", hi: "वास्तविक-प्रचलन प्रेसिज़न नहीं" },
  lim6Body: {
    en: "Headline gold precision 0.976 was measured at 89.9% gold prevalence (real pooled, n=318). No validated precision exists at anything like OIL’s real prevalence — expect it to be materially lower.",
    hi: "मुख्य गोल्ड प्रेसिज़न 0.976 मापी गई 89.9% गोल्ड प्रचलन पर (वास्तविक समूहित, n=318)। OIL के वास्तविक प्रचलन जैसी किसी स्थिति में सत्यापित प्रेसिज़न नहीं है — इसे काफ़ी कम अनुमानित करें।",
  },
  lim6Evidence: { en: "artifacts/gold/gold_metrics_final.json → headline real_pooled", hi: "artifacts/gold/gold_metrics_final.json → headline real_pooled" },
  lim7Title: { en: "Report translation unavailable", hi: "रिपोर्ट अनुवाद उपलब्ध नहीं" },
  lim7Body: {
    en: "The interface supports Hindi, but report text is not translated. Hindi and Assamese reports require human review through the language check. The evaluation dataset contains no Devanagari reports, so performance on them is unvalidated.",
    hi: "इंटरफ़ेस हिंदी में उपलब्ध है, लेकिन रिपोर्ट पाठ का अनुवाद नहीं होता। हिंदी और असमिया रिपोर्टों को भाषा जाँच के माध्यम से मानव समीक्षा की आवश्यकता है। मूल्यांकन डेटासेट में देवनागरी रिपोर्टें नहीं हैं, इसलिए उन पर प्रदर्शन सत्यापित नहीं है।",
  },
  lim7Evidence: {
    en: "docs/redesign-plan.md §6 (0 Devanagari rows) · app/gates.py language gate",
    hi: "docs/redesign-plan.md §6 (0 Devanagari rows) · app/gates.py language gate",
  },
  lim8Title: { en: "Synthetic generator identity unrecorded", hi: "संश्लिष्ट-जनक LLM की पहचान दर्ज नहीं" },
  lim8Body: {
    en: "Which LLM generated the synthetic training rows is not recorded anywhere in this repo. The synthetic share of the training data is therefore not fully reproducible.",
    hi: "संश्लिष्ट प्रशिक्षण पंक्तियाँ किस LLM से बनीं — यह रिपॉज़िटरी में कहीं दर्ज नहीं है। इसलिए प्रशिक्षण डेटा का संश्लिष्ट हिस्सा पूर्ण रूप से पुनरुत्पादित नहीं किया जा सकता।",
  },
  lim8Evidence: {
    en: "data_pipeline/merge_corpus.py · data_pipeline/qa_synthetic.py (no generator id recorded)",
    hi: "data_pipeline/merge_corpus.py · data_pipeline/qa_synthetic.py (no generator id recorded)",
  },
  lim9Title: {
    en: "Two IOGP rules are declared out of scope and not scored",
    hi: "दो IOGP नियम स्कोप-से-बाहर घोषित हैं और स्कोर नहीं किए जाते",
  },
  lim9Body: {
    en: "Permit to Work and Bypassing Safety Controls have no model rule scores because the training text does not identify them reliably. Seven other rules are scored. Explicit missing-permit language may still trigger a separate safeguard check.",
    hi: "प्रशिक्षण पाठ में विश्वसनीय पहचान न होने के कारण परमिट टू वर्क और सेफ्टी कंट्रोल्स बाईपास के मॉडल नियम स्कोर नहीं हैं। सात अन्य नियमों के स्कोर हैं। परमिट की स्पष्ट अनुपस्थिति अलग सुरक्षा जाँच को फिर भी सक्रिय कर सकती है।",
  },
  lim9Evidence: {
    en: "app/explain.py RULE_DISPLAY · docs/redesign-plan.md §8",
    hi: "app/explain.py RULE_DISPLAY · docs/redesign-plan.md §8",
  },
} as const;

export type SettingsKey = keyof typeof S;

export function t(lang: Lang, key: SettingsKey): string {
  return S[key][lang];
}

/** t() with {var} interpolation for computed counts. */
export function tf(
  lang: Lang,
  key: Extract<SettingsKey, "gatesBadgeSummary" | "gatesGraySummary">,
  vars: { n: number; total?: number; pct: number },
): string {
  return t(lang, key).replace(/\{(\w+)\}/g, (_, k: string) =>
    k in vars ? String(vars[k as keyof typeof vars]) : `{${k}}`,
  );
}
