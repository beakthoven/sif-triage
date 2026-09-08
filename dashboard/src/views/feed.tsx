import { useState } from "react";
import { BandBadge } from "@/components/band-badge";
import { GrayStateCard, SentinelGateLegend } from "@/components/gray-state-card";
import { TriageCard } from "@/components/triage-card";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { t, type Lang } from "@/lib/phrasebook";
import type { Report } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Feed: report queue + triage card with evidence highlights. Gray-action
 *  gates (min_length/negation/language/confidence/drill) swap the card for
 *  Sentinel gray-state cards; badge-action gates (near_dup, long_input)
 *  annotate the triage card itself. */
export function FeedView({
  reports,
  lang,
  onOverride,
}: {
  reports: Report[];
  lang: Lang;
  onOverride: (reportId: number, decision: "confirm" | "not_sif") => void;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = reports.find((r) => r.id === selectedId) ?? reports[0];

  if (!selected) {
    return (
      <div className="space-y-6">
        <Card className="border-border">
          <CardContent className="px-5 py-8 text-center text-muted-foreground">
            No reports yet. Ingest via{" "}
            <code className="font-mono text-foreground">POST /api/ingest</code>{" "}
            and the queue will populate here.
          </CardContent>
        </Card>
        <SentinelGateLegend />
      </div>
    );
  }

  const grayGates = (r: Report) =>
    r.prediction.gate_states.filter((g) => g.triggered && g.action !== "badge");
  const triggered = grayGates(selected);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(320px,1fr)_2fr]">
        {/* Report queue */}
        <Card className="self-start border-border py-0">
          <CardContent className="px-0 py-0">
            <p className="px-4 pt-3 pb-2 font-mono text-xs tracking-wide text-muted-foreground uppercase">
              {t(lang, "reportQueue")} · {reports.length}
            </p>
            <Separator />
            <ul>
              {reports.map((r) => {
                const gated = grayGates(r).length > 0;
                const dup = r.prediction.gate_states.some(
                  (g) => g.name === "near_dup" && g.triggered,
                );
                const active = r.id === selected.id;
                return (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(r.id)}
                      aria-current={active}
                      className={cn(
                        "flex min-h-11 w-full items-center gap-3 px-4 py-2.5 text-left transition-colors",
                        active ? "bg-accent" : "hover:bg-muted/60",
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-foreground">
                          {r.site}
                        </span>
                        <span className="block font-mono text-xs text-muted-foreground">
                          #{r.id} · {r.reported_at}
                        </span>
                      </span>
                      {dup && !gated && (
                        <span className="rounded-sm border border-primary/60 bg-primary/10 px-1.5 py-0.5 font-mono text-xs font-semibold text-primary">
                          DUP
                        </span>
                      )}
                      {gated ? (
                        <span className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                          GATE
                        </span>
                      ) : (
                        <BandBadge band={r.prediction.band} className="px-1.5 py-0.5 text-xs" />
                      )}
                    </button>
                    <Separator />
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        {/* Selected report: triage card, or gray-state card(s) if gated */}
        <div className="space-y-4">
          {triggered.length > 0 ? (
            triggered.map((g) => (
              <GrayStateCard key={g.name} report={selected} gate={g} />
            ))
          ) : (
            <TriageCard report={selected} lang={lang} onOverride={onOverride} />
          )}
        </div>
      </div>

      <SentinelGateLegend />
    </div>
  );
}
