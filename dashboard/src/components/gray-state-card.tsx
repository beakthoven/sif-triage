import { ArrowLeftRight, Copy, Info, Languages } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { GateKind, Report } from "@/lib/types";

/**
 * The 4 engineered gray states — one "Sentinel gate" system, four honest
 * behaviors. Slate (never red/error styling), icon + one plain sentence,
 * "routed to review — never auto-cleared".
 */
const GATE_META: Record<
  GateKind,
  { icon: typeof Info; name: string; sentence: string }
> = {
  low_confidence: {
    icon: Info,
    name: "Low confidence",
    sentence:
      "Score below the calibrated threshold τ — not enough signal to rank. Routed to review, never auto-cleared.",
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
      "Hindi detected → translated → scored, shown as a pipeline. Original text preserved. Routed to review, never auto-cleared.",
  },
  near_dup: {
    icon: Copy,
    name: "Near-duplicate",
    sentence:
      "Matches a training record — memory, not generalization. Routed to review, never auto-cleared.",
  },
};

export function GrayStateCard({ report, gate }: { report: Report; gate: GateKind }) {
  const meta = GATE_META[gate];
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
        {gate === "language" && (
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
          {report.id} · {report.site} · {report.activity}
        </p>
      </CardContent>
    </Card>
  );
}

/** Uniform 4-card legend of the whole gate system (demo-visible humility). */
export function SentinelGateLegend() {
  const gates: GateKind[] = ["low_confidence", "negation", "language", "near_dup"];
  return (
    <section aria-label="Sentinel gate system">
      <h2 className="mb-3 font-mono text-sm tracking-wide text-muted-foreground uppercase">
        The Sentinel gate system — routed to review, never auto-cleared
      </h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {gates.map((g) => {
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
