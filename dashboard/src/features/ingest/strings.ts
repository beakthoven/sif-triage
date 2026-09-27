/* INGEST-slice phrasebook (EN/हिं). The shared phrasebook is @/lib/phrasebook
 * (SHELL-owned); this module only adds keys this feature introduces. Shared
 * keys (pasteTitle, pastePlaceholder, pasteButton, pasteBusy, pasteHint,
 * offlineNote, triageScore, flaggedFor, highPriority, moderatePriority,
 * noAction, demoDisclosure) are used via the shared t(). */

import type { Lang, StringKey } from "@/lib/phrasebook";

const STRINGS = {
  ingestEyebrow: { en: "Safety workspace", hi: "सुरक्षा कार्यक्षेत्र" },
  ingestTitle: { en: "Add a safety report", hi: "सुरक्षा रिपोर्ट जोड़ें" },
  inputHeading: { en: "New report", hi: "नई रिपोर्ट" },
  resultHeading: { en: "Assessment", hi: "आकलन" },
  reportTextLabel: { en: "What happened?", hi: "क्या हुआ?" },
  charCount: { en: "{n} characters", hi: "{n} अक्षर" },
  resultIdle: { en: "Your assessment appears here", hi: "आपका आकलन यहाँ दिखेगा" },
  resultIdleBody: {
    en: "Add the report details to see its priority and the key evidence behind it.",
    hi: "प्राथमिकता और उसके पीछे के मुख्य साक्ष्य देखने के लिए रिपोर्ट का विवरण जोड़ें।",
  },
  resultBusy: { en: "Reviewing your report…", hi: "आपकी रिपोर्ट की समीक्षा जारी…" },
  resultErrorTitle: { en: "Report assessment unavailable", hi: "रिपोर्ट का आकलन उपलब्ध नहीं" },
  bulkIdle: { en: "Ready to import", hi: "आयात के लिए तैयार" },
  bulkIdleBody: {
    en: "Select a CSV to add multiple reports at once. Progress will appear here.",
    hi: "एक साथ कई रिपोर्ट जोड़ने के लिए CSV चुनें। प्रगति यहाँ दिखाई देगी।",
  },
  dropTitle: { en: "Drop a CSV file here", hi: "CSV फ़ाइल यहाँ छोड़ें" },
  dropOr: { en: "or", hi: "या" },
  dropActive: { en: "Release to load this file", hi: "यह फ़ाइल लोड करने के लिए छोड़ें" },
  demoTitle: { en: "Explore with sample data", hi: "नमूना डेटा के साथ देखें" },
  demoRun: { en: "Try Sample Import", hi: "नमूना आयात आज़माएँ" },
  openReport: { en: "View Report", hi: "रिपोर्ट देखें" },
  classifyAnother: { en: "Add Another", hi: "एक और जोड़ें" },
  openQueue: { en: "Open Reports History", hi: "रिपोर्ट इतिहास खोलें" },
  latencyLabel: { en: "Latency", hi: "विलंब" },
  modelLabel: { en: "Model", hi: "मॉडल" },
  runningTitle: { en: "Import in progress", hi: "आयात जारी" },
  bulkRunningElsewhere: {
    en: "CSV import in progress. {done} rows classified.",
    hi: "CSV आयात जारी है। {done} पंक्तियाँ वर्गीकृत।",
  },
  viewProgress: { en: "View progress", hi: "प्रगति देखें" },
  netChange: { en: "database count change", hi: "डेटाबेस की गिनती में बदलाव" },
  ingestSub: {
    en: "Record the incident and assess its review priority.",
    hi: "घटना दर्ज करें और उसकी समीक्षा प्राथमिकता का आकलन करें।",
  },
  tabSingle: { en: "Single report", hi: "एक रिपोर्ट" },
  tabBulk: { en: "Import CSV", hi: "CSV आयात करें" },
  pasteNote: {
    en: "Submitted reports are added to the report register.",
    hi: "प्रस्तुत रिपोर्टें रिपोर्ट पंजिका में जोड़ी जाती हैं।",
  },
  chooseCsv: { en: "Select CSV", hi: "CSV चुनें" },
  csvAliasHint: {
    en: "Include a report description column. Date, location, activity and contractor details are optional.",
    hi: "रिपोर्ट विवरण वाला कॉलम शामिल करें। तारीख, स्थान, गतिविधि और ठेकेदार का विवरण वैकल्पिक है।",
  },
  csvAliasHintSynthetic: {
    en: "500 synthetic reports, not real incident records.",
    hi: "500 कृत्रिम रिपोर्टें, वास्तविक घटना रिकॉर्ड नहीं।",
  },
  rowsSelected: { en: "About {n} data rows", hi: "लगभग {n} डेटा पंक्तियाँ" },
  rowsSelectedUnknown: {
    en: "Row count available after import starts",
    hi: "आयात शुरू होने पर पंक्तियों की गिनती उपलब्ध होगी",
  },
  startIngest: { en: "Start ingest", hi: "आयात शुरू करें" },
  demoButton: { en: "Demo batch (synthetic data)", hi: "डेमो बैच (कृत्रिम डेटा)" },
  demoDialogTitle: { en: "Run the demo batch?", hi: "डेमो बैच चलाएँ?" },
  demoDialogBody: {
    en: "Add 500 synthetic OIL-style reports to the register. These are not real incident records. Import may take several minutes; identical uploads are not imported twice.",
    hi: "पंजिका में OIL शैली की 500 कृत्रिम रिपोर्टें जोड़ें। ये वास्तविक घटना रिकॉर्ड नहीं हैं। आयात में कई मिनट लग सकते हैं; एक ही फ़ाइल दोबारा आयात नहीं होती।",
  },
  csvDialogTitle: { en: "Import {name}?", hi: "{name} आयात करें?" },
  csvDialogBody: {
    en: "About {n} rows will be assessed and added to the register. Invalid rows are reported separately. Large files may take several minutes.",
    hi: "लगभग {n} पंक्तियों का आकलन करके पंजिका में जोड़ा जाएगा। अमान्य पंक्तियाँ अलग दिखाई जाएँगी। बड़ी फ़ाइलों में कई मिनट लग सकते हैं।",
  },
  dialogCancel: { en: "Cancel", hi: "रद्द करें" },
  statusStarting: { en: "Starting…", hi: "शुरू हो रहा है…" },
  statusRunning: { en: "Running", hi: "चल रहा है" },
  progressRows: {
    en: "{done} of {total} rows classified",
    hi: "{total} में से {done} पंक्तियाँ वर्गीकृत",
  },
  progressDoneSoFar: { en: "{done} rows classified", hi: "{done} पंक्तियाँ वर्गीकृत" },
  progressEta: { en: "est. {s}s remaining", hi: "अनुमानित {s} सेकंड शेष" },
  progressMeasuring: { en: "measuring speed…", hi: "गति मापी जा रही है…" },
  progressRate: { en: "{r} rows/s", hi: "{r} पंक्तियाँ/सेकंड" },
  elapsedLabel: { en: "elapsed", hi: "बीता समय" },
  cancelJob: { en: "Cancel import", hi: "आयात रद्द करें" },
  cancelRequested: {
    en: "Cancellation requested. Awaiting confirmation…",
    hi: "रद्द करने का अनुरोध भेजा गया। पुष्टि की प्रतीक्षा…",
  },
  abortWait: { en: "Stop waiting", hi: "प्रतीक्षा रोकें" },
  abortWaitHint: {
    en: "Stops waiting for the response, not the import.",
    hi: "उत्तर की प्रतीक्षा रुकती है, आयात नहीं।",
  },
  noJobApi: {
    en: "Row progress is unavailable while awaiting the import result.",
    hi: "आयात परिणाम की प्रतीक्षा के दौरान पंक्ति प्रगति उपलब्ध नहीं है।",
  },
  verifying: {
    en: "Checking for stored reports…",
    hi: "संग्रहीत रिपोर्टें जाँची जा रही हैं…",
  },
  timeoutTruth: {
    en: "The response was not received. Stored reports increased from {before} to {after} (+{delta}), but this batch's completion is unconfirmed. Retry the same file to retrieve its result without importing it twice.",
    hi: "उत्तर नहीं मिला। संग्रहीत रिपोर्टें {before} से {after} हुईं (+{delta}), लेकिन इस बैच के पूरा होने की पुष्टि नहीं है। परिणाम पाने के लिए वही फ़ाइल फिर भेजें; वह दोबारा आयात नहीं होगी।",
  },
  timeoutNoChange: {
    en: "No result was received after {s}s. The batch remains unconfirmed after a {w}s check; processing may continue. Retry the same file to check its result without importing it twice.",
    hi: "{s} सेकंड बाद भी परिणाम नहीं मिला। {w} सेकंड की जाँच के बाद भी बैच की पुष्टि नहीं हुई; प्रक्रिया जारी हो सकती है। परिणाम जाँचने के लिए वही फ़ाइल फिर भेजें; वह दोबारा आयात नहीं होगी।",
  },
  outcomeTitle: { en: "Outcome", hi: "परिणाम" },
  acceptedLabel: { en: "accepted", hi: "स्वीकृत" },
  rejectedLabel: { en: "rejected", hi: "अस्वीकृत" },
  duplicatesLabel: { en: "duplicates skipped", hi: "डुप्लिकेट छोड़े गए" },
  receivedLabel: { en: "received", hi: "प्राप्त" },
  verifiedByCount: {
    en: "Database count increased; batch result unavailable",
    hi: "डेटाबेस की गिनती बढ़ी; बैच परिणाम अनुपलब्ध",
  },
  indeterminateStatus: {
    en: "outcome not confirmed",
    hi: "परिणाम पुष्ट नहीं",
  },
  replayNote: {
    en: "This file was already processed. Its saved result is shown.",
    hi: "इस फ़ाइल पर पहले ही प्रक्रिया हो चुकी है। उसका सहेजा परिणाम दिखाया गया है।",
  },
  errorsTitle: { en: "Rejected rows ({n})", hi: "अस्वीकृत पंक्तियाँ ({n})" },
  colRow: { en: "CSV row", hi: "CSV पंक्ति" },
  colError: { en: "Reason", hi: "कारण" },
  noErrors: { en: "No rejected rows.", hi: "कोई अस्वीकृत पंक्ति नहीं।" },
  statusDone: { en: "completed", hi: "पूर्ण" },
  statusCancelled: { en: "cancelled", hi: "रद्द" },
  statusFailed: { en: "failed", hi: "विफल" },
  statusIndeterminate: { en: "not confirmed", hi: "पुष्ट नहीं" },
  statusDoneVerified: { en: "outcome not confirmed", hi: "परिणाम पुष्ट नहीं" },
  cancelUnavailable: {
    en: "The import could not be cancelled. It may still be processing; progress will continue to update.",
    hi: "आयात रद्द नहीं हो सका। प्रक्रिया जारी हो सकती है; प्रगति अपडेट होती रहेगी।",
  },
  pollLost: {
    en: "Import progress is unavailable. The outcome is unconfirmed. Retry the same file to check its result without importing it twice.",
    hi: "आयात प्रगति उपलब्ध नहीं है। परिणाम की पुष्टि नहीं हुई है। परिणाम जाँचने के लिए वही फ़ाइल फिर भेजें; वह दोबारा आयात नहीं होगी।",
  },
  pasteStored: { en: "Stored as report #{id}", hi: "रिपोर्ट #{id} के रूप में संग्रहीत" },
  pasteNotStored: { en: "Not stored", hi: "संग्रहीत नहीं" },
  pasteGates: { en: "Review checks", hi: "समीक्षा जाँच" },
  pasteNoGates: { en: "No review checks triggered", hi: "कोई समीक्षा जाँच सक्रिय नहीं" },
  serverRejected: {
    en: "Import failed: {detail}",
    hi: "आयात विफल: {detail}",
  },
  fileEmpty: {
    en: "The selected file contains no data rows.",
    hi: "चयनित फ़ाइल में कोई डेटा पंक्तियाँ नहीं हैं।",
  },
  fileReadFailed: {
    en: "Could not read this file. Select it again or choose another CSV.",
    hi: "यह फ़ाइल पढ़ी नहीं जा सकी। इसे फिर चुनें या दूसरी CSV चुनें।",
  },
  demoUnavailable: {
    en: "Sample file unavailable. Try again or select your own CSV.",
    hi: "नमूना फ़ाइल उपलब्ध नहीं है। पुनः प्रयास करें या अपनी CSV चुनें।",
  },
  bandUnavailable: {
    en: "Review priority unavailable",
    hi: "समीक्षा प्राथमिकता अनुपलब्ध",
  },
  rowsStat: { en: "rows", hi: "पंक्तियाँ" },
  fileReading: { en: "Reading file…", hi: "फ़ाइल पढ़ी जा रही है…" },
  pasteTimeout: {
    en: "Assessment unavailable. Try again shortly.",
    hi: "आकलन उपलब्ध नहीं है। कुछ देर बाद पुनः प्रयास करें।",
  },
} as const;

export type IngestStringKey = keyof typeof STRINGS;

/** Same contract as @/lib/phrasebook's t(), with {param} interpolation. */
export function t(
  lang: Lang,
  key: IngestStringKey,
  params?: Record<string, string | number>,
): string {
  let s: string = STRINGS[key][lang];
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      s = s.replaceAll(`{${k}}`, String(v));
    }
  }
  return s;
}

export type { Lang, StringKey };