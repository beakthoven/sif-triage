import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { t, type Lang } from "@/lib/phrasebook";
import { reportActivityLabel, reportSiteLabel } from "@/lib/report-display";
import type { GateKind, GateState, Report } from "@/lib/types";

/**
 * The gate system — one honesty UI for the 10 input gates (app/gates.py).
 * Slate (never red/error styling), a quiet dot + one plain sentence,
 * "routed to review — never auto-cleared". Gates annotate; they never block.
 */
const GATE_META: Record<
  GateKind,
  { name: string; sentence: string; hiName: string; hiSentence: string }
> = {
  min_length: {
    name: "Very short report",
    sentence:
      "Very short text with no recognized safety short code — not enough signal to score reliably. Routed to review, never auto-cleared.",
    hiName: "बहुत छोटी रिपोर्ट",
    hiSentence: "विश्वसनीय स्कोर के लिए पर्याप्त जानकारी नहीं है। इसे मानवीय समीक्षा में भेजा गया है।",
  },
  negation: {
    name: "Negation detected",
    sentence:
      "\u2018No injury\u2019 phrasing detected — the model may be reading outcome words, not mechanism. Routed to review, never auto-cleared.",
    hiName: "नकारात्मक वाक्य मिला",
    hiSentence: "मॉडल घटना के कारण के बजाय परिणाम के शब्द पढ़ सकता है। इसे मानवीय समीक्षा में भेजा गया है।",
  },
  language: {
    name: "Language not currently scored",
    sentence:
      "Language beyond current scoring support — the original text is preserved and routed to review, never silently mis-scored.",
    hiName: "यह भाषा अभी स्कोर नहीं की जाती",
    hiSentence: "मूल पाठ सुरक्षित रखा गया है और गलत स्कोर देने के बजाय मानवीय समीक्षा में भेजा गया है।",
  },
  confidence: {
    name: "Uncertain score",
    sentence:
      "The score sits in the uncertain band — not enough signal to rank confidently. Routed to review, never auto-cleared.",
    hiName: "अनिश्चित स्कोर",
    hiSentence: "विश्वसनीय प्राथमिकता तय करने के लिए संकेत पर्याप्त नहीं है। इसे मानवीय समीक्षा में भेजा गया है।",
  },
  drill: {
    name: "Report mentions a drill or test",
    sentence:
      "Drill or exercise language detected — a rehearsal is not a precursor. Routed to review, never auto-cleared.",
    hiName: "रिपोर्ट में ड्रिल या परीक्षण का उल्लेख है",
    hiSentence: "अभ्यास वास्तविक घटना नहीं है। रिपोर्ट को मानवीय समीक्षा में भेजा गया है।",
  },
  near_dup: {
    name: "Possible duplicate of a training record",
    sentence:
      "Matches a training record — memory, not generalization. Shown as a banner on the triage card.",
    hiName: "प्रशिक्षण रिकॉर्ड का संभावित डुप्लिकेट",
    hiSentence: "यह प्रशिक्षण रिकॉर्ड से मेल खाता है — सामान्यीकरण नहीं, स्मृति।",
  },
  long_input: {
    name: "Long report, scored in sections",
    sentence:
      "Over 120 words — scored section by section, since very long reports are rare in training. Marked as \u2018scored in sections\u2019 on the card.",
    hiName: "लंबी रिपोर्ट, खंडों में स्कोर",
    hiSentence: "लंबी रिपोर्ट को अधिक विश्वसनीय परिणाम के लिए खंडों में स्कोर किया गया है।",
  },
  well_control_watch: {
    name: "Possible well-control concern",
    sentence:
      "Well-control/barrier language detected, but the triage score is below the flag threshold — a rare, high-consequence domain where automated screening defers. Routed to human review, never auto-cleared.",
    hiName: "संभावित वेल-कंट्रोल चिंता",
    hiSentence: "वेल-कंट्रोल या अवरोध भाषा मिली है। दुर्लभ और गंभीर जोखिम के कारण इसे मानवीय समीक्षा में भेजा गया है।",
  },
  chunked_low_score: {
    name: "Long report with uncertain score",
    sentence:
      "A long report scored in sections landed in the uncertain band — section scoring can discount mid-text hazards. Routed to human review, never auto-cleared.",
    hiName: "अनिश्चित स्कोर वाली लंबी रिपोर्ट",
    hiSentence: "खंडों में स्कोर की गई रिपोर्ट अनिश्चित श्रेणी में है। इसे मानवीय समीक्षा में भेजा गया है।",
  },
  severity_watch: {
    name: "Serious-event language, low score",
    sentence:
      "The report mentions an injury or high-energy event, but the score is low — the model may have missed it. Routed to human review, never auto-cleared.",
    hiName: "गंभीर घटना की भाषा, कम स्कोर",
    hiSentence: "रिपोर्ट में चोट या उच्च-ऊर्जा घटना का उल्लेख है, पर स्कोर कम है — मॉडल इसे चूक सकता है। इसे मानवीय समीक्षा में भेजा गया है।",
  },
};

const GATE_ORDER: GateKind[] = [
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
];

export function GrayStateCard({
  report,
  gate,
  lang,
  reviewed = false,
  onOverride,
}: {
  report: Report;
  gate: GateState;
  lang: Lang;
  reviewed?: boolean;
  onOverride?: (reportId: number, decision: "confirm" | "not_sif") => void;
}) {
  const meta = GATE_META[gate.name];
  const name = lang === "hi" ? meta.hiName : meta.name;
  const sentence = lang === "hi" ? meta.hiSentence : meta.sentence;
  const activity = reportActivityLabel(report);
  const [decision, setDecision] = useState<"confirm" | "not_sif" | null>(null);

  function decide(next: "confirm" | "not_sif") {
    setDecision(next);
    onOverride?.(report.id, next);
  }

  return (
    <Card className="gap-0 border-border py-0">
      <CardHeader className="gap-1">
        <p className="flex items-center gap-2 text-xs font-medium text-quiet">
          <span className="status-dot bg-quiet" aria-hidden />
          {t(lang, "manualReview")}
        </p>
        <h3 className="text-xl font-semibold text-foreground">{name}</h3>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-muted-foreground">{sentence}</p>
        <blockquote className="border-l-2 border-border pl-4 text-foreground/80 italic">
          {report.text}
        </blockquote>
        <p className="font-mono text-xs text-muted-foreground">
          {reportSiteLabel(report)}
          {activity ? ` · ${activity}` : ""} · {report.reported_at}
        </p>
        {gate.detail && (
          <details>
            <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
              {t(lang, "technicalDetail")}
            </summary>
            <p className="mt-2 font-mono text-xs text-muted-foreground/70">{gate.detail}</p>
          </details>
        )}
      </CardContent>
      <CardFooter className="flex flex-wrap gap-3 border-t border-border px-6 py-4 [.border-t]:pt-4">
        {reviewed ? (
          <span className="inline-flex items-center gap-2 text-sm font-medium text-ok">
            <span className="status-dot bg-ok" aria-hidden />
            {t(lang, "alreadyReviewed")}
          </span>
        ) : (
          <>
            <Button
              size="lg"
              variant={decision === "confirm" ? "default" : "outline"}
              onClick={() => decide("confirm")}
            >
              {t(lang, "confirm")}
            </Button>
            <Button
              size="lg"
              variant={decision === "not_sif" ? "default" : "outline"}
              onClick={() => decide("not_sif")}
            >
              {t(lang, "notSif")}
            </Button>
            {decision && (
              <span role="status" className="text-sm font-medium text-ok">
                {t(lang, "decisionSaved")}
              </span>
            )}
          </>
        )}
      </CardFooter>
    </Card>
  );
}

/** Uniform legend of the whole gate system (demo-visible humility) — one
 *  card, hairline-divided rows, no per-gate boxes. */
export function SentinelGateLegend({ lang }: { lang: Lang }) {
  return (
    <section aria-label="Sentinel gate system">
      <Card className="gap-0 border-0 bg-transparent py-0 shadow-none">
        <ul>
          {GATE_ORDER.map((g) => {
            const meta = GATE_META[g];
            const name = lang === "hi" ? meta.hiName : meta.name;
            const sentence = lang === "hi" ? meta.hiSentence : meta.sentence;
            return (
              <li
                key={g}
                className="flex items-baseline gap-3 border-b border-border px-5 py-3 last:border-b-0"
              >
                <span className="status-dot relative -translate-y-0.5 bg-quiet" aria-hidden />
                <p className="text-sm">
                  <span className="font-medium text-foreground">{name}.</span>{" "}
                  <span className="text-muted-foreground">{sentence}</span>
                </p>
              </li>
            );
          })}
        </ul>
      </Card>
    </section>
  );
}
