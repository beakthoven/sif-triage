/* Analytics phrasebook (EN/हिं) — feature-local until SHELL merges these keys
 * into @/lib/phrasebook.ts (lib/** is outside the ANALYTICS slice). Same
 * {en, hi} shape and call convention as the global phrasebook so the merge is
 * a copy-paste. No user-facing string lives inline in the feature files. */

import type { Lang } from "@/lib/phrasebook";

const STRINGS = {
  analyticsEyebrow: { en: "Safety insights", hi: "सुरक्षा अंतर्दृष्टि" },
  analyticsTitle: { en: "Risk trends", hi: "जोखिम रुझान" },
  analyticsSub: {
    en: "See how flagged reports change over time, where they concentrate and which conditions recur.",
    hi: "देखें कि चिह्नित रिपोर्टें समय के साथ कैसे बदलती हैं, कहाँ केंद्रित हैं और कौन-सी स्थितियाँ दोहराती हैं।",
  },
  liveDbChip: { en: "Live database", hi: "लाइव डेटाबेस" },
  reportCoverage: { en: "{count} reports analysed", hi: "{count} रिपोर्टों का विश्लेषण" },
  truncatedReports: {
    en: "first 10,000 reports analysed — register truncated for this view",
    hi: "पहली 10,000 रिपोर्टों का विश्लेषण — इस दृश्य के लिए रजिस्टर सीमित है",
  },
  thresholdUnverified: {
    en: "Review threshold unverified; counts use a fallback threshold",
    hi: "समीक्षा सीमा अप्रमाणित है; गिनती वैकल्पिक सीमा पर आधारित है",
  },
  thresholdSummary: {
    en: "Reports scoring {threshold} or higher are flagged",
    hi: "{threshold} या अधिक स्कोर वाली रिपोर्टें चिह्नित हैं",
  },
  dataNotes: { en: "Data notes", hi: "डेटा टिप्पणियाँ" },
  analyticsViews: { en: "Risk trend views", hi: "जोखिम रुझान दृश्य" },
  viewTrend: { en: "Trend", hi: "रुझान" },
  viewHotspots: { en: "Hotspots", hi: "जोखिम केंद्र" },
  viewPatterns: { en: "Recurring patterns", hi: "दोहराते पैटर्न" },
  thresholdNote: {
    en: "Reports scoring {threshold} or higher are flagged at the configured review threshold.",
    hi: "निर्धारित समीक्षा सीमा {threshold} या अधिक स्कोर वाली रिपोर्टें चिह्नित हैं।",
  },
  thresholdMismatch: {
    en: "At {threshold}, this view counts {client} flagged reports; the database summary counts {server}. Treat this view's counts as approximate.",
    hi: "{threshold} पर इस दृश्य में {client} चिह्नित रिपोर्टें हैं; डेटाबेस सारांश में {server} हैं। इस दृश्य की गिनती अनुमानित मानें।",
  },
  trendTitle: { en: "Flagged reports over time", hi: "समय के साथ चिह्नित रिपोर्टें" },
  trendSub: {
    en: "Track the flagged rate alongside report volume. The line shows flagged reports per 100; bars show total reports.",
    hi: "रिपोर्ट संख्या के साथ चिह्नित दर देखें। रेखा प्रति 100 चिह्नित रिपोर्टें और सलाखें कुल रिपोर्टें दिखाती हैं।",
  },
  granularityWeek: { en: "Weekly", hi: "साप्ताहिक" },
  granularityMonth: { en: "Monthly", hi: "मासिक" },
  period: { en: "Period", hi: "अवधि" },
  window: { en: "Window", hi: "समय-सीमा" },
  customWindow: { en: "Custom range", hi: "अनुकूलित सीमा" },
  allDates: { en: "All dates", hi: "सभी तारीखें" },
  selectDateRange: { en: "Select date range", hi: "तारीख सीमा चुनें" },
  patternKind: { en: "Cell type", hi: "सेल प्रकार" },
  patternBlurb: {
    en: "Find combinations of work, location and failed barriers that appear together more often than expected.",
    hi: "काम, स्थान और विफल अवरोधों के उन संयोजनों को खोजें जो अपेक्षा से अधिक बार साथ दिखाई देते हैं।",
  },
  noFabricatedData: {
    en: "Could not load report data. Try again shortly.",
    hi: "रिपोर्ट डेटा लोड नहीं हो सका। कुछ देर बाद पुनः प्रयास करें।",
  },
  last90: { en: "Last 90 days", hi: "पिछले 90 दिन" },
  last12m: { en: "Last 12 months", hi: "पिछले 12 महीने" },
  allTime: { en: "All time", hi: "पूरा समय" },
  from: { en: "From", hi: "से" },
  to: { en: "To", hi: "तक" },
  applyRange: { en: "Apply", hi: "लागू करें" },
  undatedNote: {
    en: "{undated} of {total} reports carry no date — excluded from trends and date-windowed density; included in all-time density.",
    hi: "{total} में से {undated} रिपोर्टों पर तारीख नहीं है — रुझान और तारीख-सीमित घनत्व से बाहर; पूरे समय के घनत्व में शामिल।",
  },
  noDatedReports: {
    en: "No dated reports in this window. Widen the date range to see the trend.",
    hi: "इस अवधि में कोई तारीख वाली रिपोर्ट नहीं। रुझान देखने के लिए समय-सीमा बढ़ाएँ।",
  },
  reportsAxis: { en: "reports in period", hi: "अवधि की रिपोर्टें" },
  rateAxis: { en: "flagged per 100", hi: "प्रति 100 चिह्नित" },
  deltaLabel: {
    en: "Last {k} {unit} vs previous {k}",
    hi: "पिछले {k} {unit} बनाम उससे पहले के {k}",
  },
  unitWeek: { en: "weeks", hi: "सप्ताह" },
  unitMonth: { en: "months", hi: "महीने" },
  reportsShort: { en: "reports", hi: "रिपोर्टें" },
  flaggedShort: { en: "flagged", hi: "चिह्नित" },
  patternCount: { en: "n {n}", hi: "n {n}" },
  patternFlagged: { en: "flagged {flagged}", hi: "चिह्नित {flagged}" },
  patternRate: { en: "rate {rate}%", hi: "दर {rate}%" },
  patternRateCi: {
    en: "95% CI (rate) [{low}–{high}%]",
    hi: "95% CI (दर) [{low}–{high}%]",
  },
  patternLift: { en: "lift {lift}", hi: "लिफ्ट {lift}" },
  showMorePatternRows: {
    en: "Show {count} more returned patterns",
    hi: "लौटाए गए {count} और पैटर्न दिखाएँ",
  },
  showTopPatternRows: { en: "Show top 10 only", hi: "केवल शीर्ष 10 दिखाएँ" },
  densityTitle: { en: "Risk hotspots", hi: "जोखिम केंद्र" },
  densitySub: {
    en: "Compare sites, activities or contractors by flagged rate. Small samples are kept out of the ranking.",
    hi: "चिह्नित दर के आधार पर साइट, गतिविधि या ठेकेदार की तुलना करें। छोटे नमूनों को रैंकिंग से बाहर रखा जाता है।",
  },
  facetSite: { en: "Site", hi: "साइट" },
  facetActivity: { en: "Activity", hi: "गतिविधि" },
  facetContractor: { en: "Contractor", hi: "ठेकेदार" },
  facet: { en: "Facet", hi: "पहलू" },
  minN: { en: "Minimum reports to rank", hi: "रैंक के लिए न्यूनतम रिपोर्टें" },
  rankedByWilson: { en: "Wilson lower bound", hi: "Wilson निचली सीमा" },
  rankedByRate: { en: "Raw rate", hi: "कच्ची दर" },
  ranking: { en: "Ranking", hi: "क्रम" },
  colRank: { en: "Rank", hi: "रैंक" },
  colReports: { en: "Reports", hi: "रिपोर्टें" },
  colFlagged: { en: "Flagged", hi: "चिह्नित" },
  colRate: { en: "Flag rate / 100", hi: "चिह्नित दर / 100" },
  colCi: { en: "95% CI of the rate", hi: "दर का 95% CI" },
  colCiShort: { en: "95% CI (rate)", hi: "95% CI (दर)" },
  colWilsonLb: { en: "Wilson lower bound / 100", hi: "Wilson निचली सीमा / 100" },
  quarantineNote: {
    en: "{count} groups have fewer than {minN} reports and are listed separately, not ranked.",
    hi: "{count} समूहों में {minN} से कम रिपोर्टें हैं; उन्हें अलग दिखाया गया है, रैंक नहीं किया गया।",
  },
  rankedByHint: {
    en: "The Wilson lower bound accounts for sample size and uncertainty. Raw rate ranks only the observed percentage.",
    hi: "Wilson निचली सीमा नमूने के आकार और अनिश्चितता को ध्यान में रखती है। कच्ची दर केवल देखे गए प्रतिशत से क्रम बनाती है।",
  },
  showAllRanked: { en: "Show all ranked rows ({count})", hi: "सभी क्रमित पंक्तियाँ दिखाएँ ({count})" },
  showTopRanked: { en: "Show top 15 only", hi: "केवल शीर्ष 15 दिखाएँ" },
  confidenceNote: {
    en: "Confidence ranges show uncertainty in each flagged rate; wider ranges usually mean fewer reports.",
    hi: "विश्वास सीमा प्रत्येक चिह्नित दर की अनिश्चितता दिखाती है; चौड़ी सीमा आम तौर पर कम रिपोर्टों का संकेत है।",
  },
  movementNote: {
    en: "Rank changes are unavailable because historical rankings are not recorded.",
    hi: "पुरानी रैंकिंग दर्ज न होने के कारण रैंक बदलाव उपलब्ध नहीं हैं।",
  },
  emptyRanked: {
    en: "No group has enough reports to rank. Reduce the minimum report count.",
    hi: "किसी समूह में रैंकिंग के लिए पर्याप्त रिपोर्टें नहीं हैं। न्यूनतम रिपोर्ट गिनती घटाएँ।",
  },
  densityChartTitle: { en: "Top ranked: flag rate with 95% Wilson CI", hi: "शीर्ष रैंक: 95% Wilson CI सहित चिह्नित दर" },
  patternsTitle: { en: "Recurring patterns", hi: "दोहराते पैटर्न" },
  siteXactivity: { en: "Site × activity", hi: "साइट × गतिविधि" },
  activityXbarrier: { en: "Activity × failed barrier", hi: "गतिविधि × विफल अवरोध" },
  minCellN: { en: "Minimum reports per cell", hi: "प्रति सेल न्यूनतम रिपोर्टें" },
  ciOfFlagRate: { en: "95% CI of the flag rate", hi: "चिह्नित दर का 95% CI" },
  smallSample: { en: "Small sample; wide interval", hi: "छोटा नमूना; चौड़ा अंतराल" },
  saturatedCell: { en: "All pattern groups have a 100% flagged rate", hi: "सभी पैटर्न समूहों की चिह्नित दर 100% है" },
  statisticalDetail: { en: "Statistical detail", hi: "सांख्यिकीय विवरण" },
  liftExplain: {
    en: "Lift compares the group's flagged rate with the source dataset's rate. The 95% Wilson interval describes the flagged rate, not lift.",
    hi: "लिफ्ट समूह की चिह्नित दर की तुलना स्रोत डेटासेट की दर से करती है। 95% Wilson अंतराल चिह्नित दर का है, लिफ्ट का नहीं।",
  },
  saturationNote: {
    en: "All returned groups have a 100% flagged rate. This does not imply that every report in the database is flagged.",
    hi: "सभी प्राप्त समूहों की चिह्नित दर 100% है। इसका अर्थ यह नहीं कि डेटाबेस की हर रिपोर्ट चिह्नित है।",
  },
  patternProvenance: {
    en: "Computed from stored reports at the current review threshold. Pattern counts include later imports; the hotspot date filter does not apply here.",
    hi: "मौजूदा समीक्षा सीमा पर दर्ज रिपोर्टों से गणना की गई है। बाद के आयात शामिल हैं; जोखिम केंद्र का तारीख फ़िल्टर यहाँ लागू नहीं होता।",
  },
  patternsEmpty: {
    en: "No pattern group meets the minimum report count.",
    hi: "कोई पैटर्न समूह न्यूनतम रिपोर्ट गिनती पूरी नहीं करता।",
  },
  loadingCharts: { en: "Loading charts…", hi: "चार्ट लोड हो रहे हैं…" },
  dataUnavailable: {
    en: "Analytics data unavailable",
    hi: "विश्लेषण डेटा उपलब्ध नहीं है",
  },
  retry: { en: "Retry", hi: "पुनः प्रयास" },
  loadedProgress: { en: "Indexed {loaded} reports for analysis", hi: "विश्लेषण हेतु {loaded} रिपोर्टें अनुक्रमित" },
} as const;

export type AnalyticsKey = keyof typeof STRINGS;

export function t(lang: Lang, key: AnalyticsKey, vars?: Record<string, string | number>): string {
  let out: string = STRINGS[key][lang];
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      out = out.split(`{${k}}`).join(String(v));
    }
  }
  return out;
}

/** Short month names for chart ticks (chart-only labels; tables use numbers). */
export const MONTHS: Record<Lang, string[]> = {
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  hi: ["जन", "फ़र", "मार्च", "अप्रै", "मई", "जून", "जुल", "अग", "सित", "अक्टू", "नव", "दिस"],
};