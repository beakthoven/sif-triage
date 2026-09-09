import { useRef, useState } from "react";
import { BandBadge } from "@/components/band-badge";
import { GrayStateCard, SentinelGateLegend } from "@/components/gray-state-card";
import { PasteClassify } from "@/components/paste-classify";
import { TriageCard } from "@/components/triage-card";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { classify } from "@/lib/api";
import { t, type Lang } from "@/lib/phrasebook";
import type { Report } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Feed: paste-classify box + report queue + triage card with evidence
 *  highlights. Gray-action gates (min_length/negation/language/confidence/
 *  drill/well_control_watch) swap the card for Sentinel gray-state cards;
 *  badge-action gates (near_dup, long_input) annotate the triage card itself.
 *
 *  The paste box is the demo's opening beat: POST /api/classify?persist=1
 *  stores the report server-side and returns the real row id — the pasted
 *  card joins the queue as a genuine feed row, so the override buttons POST
 *  /review against a persisted report (audit F4: negative-id placeholder
 *  rows 404'd). Offline (or an old server without persist), the row falls
 *  back to a negative-id optimistic placeholder and overrides land in the
 *  local log; the box shows the offline note — the UI never crashes. */
export function FeedView({
  reports,
  lang,
  onOverride,
  onClassified,
}: {
  reports: Report[];
  lang: Lang;
  onOverride: (reportId: number, decision: "confirm" | "not_sif") => void;
  onClassified: (report: Report) => void;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [classifying, setClassifying] = useState(false);
  const [offlineNote, setOfflineNote] = useState(false);
  // busyRef closes the same-task race the state flag can't (5 fast clicks
  // dispatch before a re-render flips `classifying`) — review SEV2-3.
  const busyRef = useRef(false);
  // Optimistic-row ids come from a counter, never re-derived from the queue —
  // raced rows must never share one id (duplicate keys, shared selection).
  // Only used when the server did not persist the paste (offline / old API).
  const nextLocalId = useRef(-1);
  const selected = reports.find((r) => r.id === selectedId) ?? reports[0];

  async function submitPaste() {
    const value = pasteText.trim();
    if (!value || busyRef.current) return;
    busyRef.current = true;
    setClassifying(true);
    setOfflineNote(false);
    try {
      const prediction = await classify(value, { explain: true });
      // The server persists the paste (persist=1) and returns the real row
      // id; offline fallback keeps the negative-id optimistic convention.
      const serverId = prediction.report_id ?? null;
      setOfflineNote(prediction.model_version === "offline" || serverId === null);
      const id =
        serverId ??
        Math.min(nextLocalId.current, 0, ...reports.map((r) => r.id)) - 1;
      if (serverId === null) nextLocalId.current = id;
      const report: Report = {
        id,
        text: value,
        site: "(live paste)",
        activity: "ad-hoc classify",
        contractor: null,
        reported_at: new Date().toISOString().slice(0, 10),
        prediction,
      };
      onClassified(report);
      setSelectedId(report.id);
    } finally {
      busyRef.current = false;
      setClassifying(false);
    }
  }

  const grayGates = (r: Report) =>
    r.prediction.gate_states.filter((g) => g.triggered && g.action !== "badge");
  const triggered = selected ? grayGates(selected) : [];

  return (
    <div className="space-y-6">
      <PasteClassify
        lang={lang}
        text={pasteText}
        busy={classifying}
        offline={offlineNote}
        onTextChange={setPasteText}
        onSubmit={submitPaste}
      />

      {!selected ? (
        <Card className="border-border">
          <CardContent className="px-5 py-8 text-center text-muted-foreground">
            No reports yet. Ingest via{" "}
            <code className="font-mono text-foreground">POST /api/ingest</code>{" "}
            and the queue will populate here.
          </CardContent>
        </Card>
      ) : (
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
                  const live = r.id < 0;
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
                            {live ? t(lang, "liveChip") : `#${r.id}`} · {r.reported_at}
                          </span>
                        </span>
                        {live && (
                          <span className="rounded-sm bg-primary px-1.5 py-0.5 font-mono text-xs font-semibold text-primary-foreground">
                            {t(lang, "liveChip")}
                          </span>
                        )}
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

          {/* Selected report: triage card, gray-state card(s) if gated, or
              the classify skeleton while a paste is in flight */}
          <div className="space-y-4">
            {classifying ? (
              <Card className="overflow-hidden border-border py-0" aria-busy="true" aria-label={t(lang, "pasteBusy")}>
                <div className="hazard-stripe h-10 w-full animate-pulse" />
                <CardContent className="space-y-3 px-5 py-5">
                  <div className="h-4 w-1/3 animate-pulse rounded-sm bg-muted" />
                  <div className="h-4 w-full animate-pulse rounded-sm bg-muted" />
                  <div className="h-4 w-5/6 animate-pulse rounded-sm bg-muted" />
                  <div className="h-4 w-2/3 animate-pulse rounded-sm bg-muted" />
                  <p className="font-mono text-xs text-muted-foreground">
                    {t(lang, "pasteBusy")}
                  </p>
                </CardContent>
              </Card>
            ) : triggered.length > 0 ? (
              triggered.map((g) => (
                <GrayStateCard key={g.name} report={selected} gate={g} />
              ))
            ) : (
              <TriageCard report={selected} lang={lang} onOverride={onOverride} />
            )}
          </div>
        </div>
      )}

      <SentinelGateLegend />
    </div>
  );
}
