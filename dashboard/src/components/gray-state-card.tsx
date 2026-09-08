import {
  ArrowLeftRight,
  Copy,
  FlaskConical,
  Gauge,
  Info,
  Languages,
  Ruler,
  Scissors,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { GateKind, GateState, Report } from "@/lib/types";

/**
 * The Sentinel gate system — one honesty UI for the 6 input gates
 * (app/gates.py). Slate (never red/error styling), icon + one plain sentence,
 * "routed to review — never auto-cleared". Gates annotate; they never block.
 */
const GATE_META: Record<
  GateKind,
  { icon: typeof Info; name: string; sentence: string }
> = {
  min_length: {
    icon: Ruler,
    name: "Short report",
    sentence:
      "Very short text with no recognized safety short code — not enough signal to score reliably. Routed to review, never auto-cleared.",
  },
  negation: {
    icon: ArrowLeftRight,
    name: "Negation guard",
    sentence:
      "\u2018No injury\u2019 phrasing detected — the model may be reading outcome words, not mechanism. Routed to review, never auto-cleared.",
  },
  language: {
    icon: Languages,
    name: "Language gate",
    sentence:
      "Language beyond current scoring support — the original text is preserved and routed to review, never silently mis-scored. Translation available on request.",
  },
  confidence: {
    icon: Gauge,
    name: "Low confidence",
    sentence:
      "Score inside the calibrated gray band τ — not enough signal to rank. Routed to review, never auto-cleared.",
  },
  drill: {
    icon: FlaskConical,
    name: "Drill / simulation",
    sentence:
      "Drill or exercise language detected — a rehearsal is not a precursor. Routed to review, never auto-cleared.",
  },
  near_dup: {
    icon: Copy,
    name: "Near-duplicate",
    sentence:
      "Matches a training record — memory, not generalization. Shown as a banner on the triage card.",
  },
  long_input: {
    icon: Scissors,
    name: "Long report (chunked)",
    sentence:
      "Over 120 words — scored with the sliding-window path (length out of distribution). Shown as a chunked badge.",
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
];

export function GrayStateCard({ report, gate }: { report: Report; gate: GateState }) {
  const meta = GATE_META[gate.name];
  const Icon = meta.icon;
  return (
    <Card className="border-border bg-muted/40">
      <CardHeader className="flex flex-row items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-md bg-secondary">
          <Icon className="size-5 text-secondary-foreground" aria-hidden />
        </span>
        <div>
          <p className="font-mono text-xs tracking-wide text-muted-foreground uppercase">
            Sentinel gate
          </p>
          <h3 className="text-lg font-semibold text-foreground">{meta.name}</h3>
        </div>
        {gate.name === "language" && (
          <span className="ml-auto rounded-sm border border-border px-2 py-0.5 font-mono text-xs text-muted-foreground">
            translation available
          </span>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-muted-foreground">{meta.sentence}</p>
        <blockquote className="border-l-2 border-border pl-4 text-foreground/80 italic">
          {report.text}
        </blockquote>
        <p className="font-mono text-xs text-muted-foreground">
          #{report.id} · {report.site} · {report.activity}
        </p>
        {gate.detail && (
          <p className="font-mono text-xs text-muted-foreground/70">{gate.detail}</p>
        )}
      </CardContent>
    </Card>
  );
}

/** Uniform legend of the whole gate system (demo-visible humility). */
export function SentinelGateLegend() {
  return (
    <section aria-label="Sentinel gate system">
      <h2 className="mb-3 font-mono text-sm tracking-wide text-muted-foreground uppercase">
        The Sentinel gate system — routed to review, never auto-cleared
      </h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {GATE_ORDER.map((g) => {
          const meta = GATE_META[g];
          const Icon = meta.icon;
          return (
            <Card key={g} className="border-border bg-muted/30">
              <CardContent className="flex-row items-start gap-3">
                <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden />
                <div>
                  <p className="font-semibold text-foreground">{meta.name}</p>
                  <p className="text-sm text-muted-foreground">{meta.sentence}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
