import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { GateKind, GateState, Report } from "@/lib/types";

/**
 * The gate system — one honesty UI for the 8 input gates (app/gates.py).
 * Slate (never red/error styling), a quiet dot + one plain sentence,
 * "routed to review — never auto-cleared". Gates annotate; they never block.
 */
const GATE_META: Record<GateKind, { name: string; sentence: string }> = {
  min_length: {
    name: "Very short report",
    sentence:
      "Very short text with no recognized safety short code — not enough signal to score reliably. Routed to review, never auto-cleared.",
  },
  negation: {
    name: "Negation detected",
    sentence:
      "\u2018No injury\u2019 phrasing detected — the model may be reading outcome words, not mechanism. Routed to review, never auto-cleared.",
  },
  language: {
    name: "Language not currently scored",
    sentence:
      "Language beyond current scoring support — the original text is preserved and routed to review, never silently mis-scored. Translation available on request.",
  },
  confidence: {
    name: "Uncertain score",
    sentence:
      "The score sits in the uncertain band — not enough signal to rank confidently. Routed to review, never auto-cleared.",
  },
  drill: {
    name: "Report mentions a drill or test",
    sentence:
      "Drill or exercise language detected — a rehearsal is not a precursor. Routed to review, never auto-cleared.",
  },
  near_dup: {
    name: "Possible duplicate of a training record",
    sentence:
      "Matches a training record — memory, not generalization. Shown as a banner on the triage card.",
  },
  long_input: {
    name: "Long report, scored in sections",
    sentence:
      "Over 120 words — scored section by section, since very long reports are rare in training. Marked as \u2018scored in sections\u2019 on the card.",
  },
  well_control_watch: {
    name: "Possible well-control concern",
    sentence:
      "Well-control/barrier language detected, but the triage score is below the flag threshold — a rare, high-consequence domain where automated screening defers. Routed to human review, never auto-cleared.",
  },
  chunked_low_score: {
    name: "Long report with uncertain score",
    sentence:
      "A long report scored in sections landed in the uncertain band — section scoring can discount mid-text hazards. Routed to human review, never auto-cleared.",
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
];

export function GrayStateCard({ report, gate }: { report: Report; gate: GateState }) {
  const meta = GATE_META[gate.name];
  return (
    <Card className="border-border">
      <CardHeader className="gap-1">
        <p className="flex items-center gap-2 text-xs font-medium text-quiet">
          <span className="status-dot bg-quiet" aria-hidden />
          Needs human review
          {gate.name === "language" && (
            <span className="ml-auto font-mono">
              translation available
            </span>
          )}
        </p>
        <h3 className="text-xl font-semibold text-foreground">{meta.name}</h3>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-muted-foreground">{meta.sentence}</p>
        <blockquote className="border-l-2 border-border pl-4 text-foreground/80 italic">
          {report.text}
        </blockquote>
        <p className="font-mono text-xs text-muted-foreground">
          {report.site === "(live paste)"
            ? report.reported_at
            : `${report.site} · ${report.activity} · ${report.reported_at}`}
        </p>
        {gate.detail && (
          <p className="font-mono text-xs text-muted-foreground/70">{gate.detail}</p>
        )}
      </CardContent>
    </Card>
  );
}

/** Uniform legend of the whole gate system (demo-visible humility) — one
 *  card, hairline-divided rows, no per-gate boxes. */
export function SentinelGateLegend() {
  return (
    <section aria-label="Sentinel gate system">
      <h2 className="mb-3 text-sm font-medium text-muted-foreground">
        Needs human review — never auto-cleared
      </h2>
      <Card className="gap-0 border-border py-0">
        <ul>
          {GATE_ORDER.map((g) => {
            const meta = GATE_META[g];
            return (
              <li
                key={g}
                className="flex items-baseline gap-3 border-b border-border px-5 py-3 last:border-b-0"
              >
                <span className="status-dot relative -translate-y-0.5 bg-quiet" aria-hidden />
                <p className="text-sm">
                  <span className="font-medium text-foreground">{meta.name}.</span>{" "}
                  <span className="text-muted-foreground">{meta.sentence}</span>
                </p>
              </li>
            );
          })}
        </ul>
      </Card>
    </section>
  );
}
