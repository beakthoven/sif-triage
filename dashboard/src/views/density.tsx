import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetchDemoIngestCsv, getDensity, getHealth, ingestCsv } from "@/lib/api";
import { DENSITY_AFTER, DENSITY_BEFORE } from "@/lib/mock";
import { t, type Lang } from "@/lib/phrasebook";
import type { DensityRow } from "@/lib/types";
import { useFlip } from "@/lib/use-flip";
import { cn } from "@/lib/utils";

/* The demo money beat: the button uploads live_ingest_500.csv — a 500-row
 * register extract (50 planted Kathalguri GCS x DG-exhaust rows + the 15 corpus
 * rows of that cell + 435 sampled rows) fetched as a static asset and POSTed
 * through the real bulk-ingest path (real parse, classification, storage,
 * ~15 s at the measured 37 rows/s). The density table is then re-fetched and
 * Kathalguri GCS visibly climbs #2 -> #1: the re-rank is real, not scripted.
 * The pre-state DB (demo_pre.db) is what makes the climb possible — restore
 * it before every run. */

function RankDelta({ delta }: { delta: number }) {
  if (delta === 0) return <span className="font-mono text-muted-foreground">0</span>;
  const up = delta > 0;
  return (
    <span
      className={cn(
        "font-mono font-medium",
        up ? "text-foreground" : "text-muted-foreground",
      )}
    >
      {up ? `+${delta}` : `−${Math.abs(delta)}`}
    </span>
  );
}

/** Density: ranked site table (GET /api/density). The demo beat — upload the
 *  500-row register extract, then rows visibly re-sort with FLIP (Kathalguri
 *  GCS climbs #2 -> #1). Offline: the scripted mock snapshots stand in (UI
 *  never hard-fails). After a real ingest, onIngested lets the app refetch
 *  the header count + feed queue (they share server state with this view). */
export function DensityView({
  lang,
  onIngested,
}: {
  lang: Lang;
  onIngested?: () => void;
}) {
  const [rows, setRows] = useState<DensityRow[]>(DENSITY_BEFORE);
  const [live, setLive] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestedOnce, setIngestedOnce] = useState(false);
  const [progress, setProgress] = useState(0);
  const [ingestNote, setIngestNote] = useState<string | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const setRowRef = useFlip(rows);

  useEffect(() => {
    let cancel = false;
    (async () => {
      const [health, density] = await Promise.all([getHealth(), getDensity("site")]);
      if (cancel) return;
      setLive(health !== null);
      setRows(density);
    })();
    return () => {
      cancel = true;
    };
  }, []);

  const topClimber = rows.find((r) => r.rank === 1 && r.prev_rank !== 1);

  // The live 500-row ingest measures ~15 s at 37 rows/s: the bar paces to 92%
  // over 16 s, then snaps to 100 on the real response (never a fake finish).
  function startProgress() {
    const start = Date.now();
    timer.current = setInterval(() => {
      setProgress(Math.min(92, ((Date.now() - start) / 16000) * 100));
    }, 50);
  }

  function stopProgress() {
    if (timer.current) clearInterval(timer.current);
    setProgress(100);
  }

  async function runIngest() {
    if (ingesting || ingestedOnce) return;
    if (live && !window.confirm(t(lang, "ingestConfirm"))) return;
    setIngesting(true);
    setProgress(0);
    setIngestError(null);
    if (live) {
      // Live beat: fetch the 500-row register extract (static asset) and POST
      // it through the bulk-ingest path, then re-fetch — ranks derived from
      // the pre-ingest snapshot drive the FLIP re-sort.
      startProgress();
      try {
        const result = await ingestCsv(await fetchDemoIngestCsv());
        setIngestNote(`accepted ${result.accepted}/${result.received}`);
        setRows(await getDensity("site", rows));
        setIngestedOnce(true);
        // The ingest changed server state — header count + feed queue refetch.
        onIngested?.();
      } catch {
        // Honest failure: keep the live rows under the LIVE badge, never
        // swap in fabricated mock numbers (review SEV2-1).
        setIngestNote(null);
        setIngestError(t(lang, "ingestFailed"));
      } finally {
        stopProgress();
        setIngesting(false);
      }
    } else {
      // Offline fallback: scripted 2s stand-in for the live beat.
      const start = Date.now();
      timer.current = setInterval(() => {
        const pct = Math.min(100, ((Date.now() - start) / 2000) * 100);
        setProgress(pct);
        if (pct >= 100) {
          if (timer.current) clearInterval(timer.current);
          setIngesting(false);
          setRows((cur) => (cur === DENSITY_BEFORE ? DENSITY_AFTER : DENSITY_BEFORE));
        }
      }, 50);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <Button
          size="lg"
          onClick={runIngest}
          disabled={ingesting || (live && ingestedOnce)}
          className="min-h-11"
        >
          {ingesting
            ? t(lang, "ingesting")
            : live && ingestedOnce
              ? t(lang, "ingestedDone")
              : t(lang, "rerank")}
        </Button>
        {(ingesting || progress > 0) && (
          <div
            role="progressbar"
            aria-valuenow={Math.round(progress)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-1.5 min-w-48 flex-1 overflow-hidden rounded-full bg-muted"
          >
            <div
              className="h-full rounded-full bg-foreground/70 transition-[width] duration-100"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
        {ingestNote && !ingesting && (
          <p className="font-mono text-xs text-muted-foreground">{ingestNote}</p>
        )}
        {ingestError && !ingesting && (
          <p role="alert" className="text-sm font-medium text-destructive">
            {ingestError}
          </p>
        )}
        {topClimber && !ingesting && (
          <p className="inline-flex items-center gap-2 text-sm font-medium text-foreground">
            <span className="status-dot bg-verdict" aria-hidden />
            {topClimber.key} just climbed to #1.
          </p>
        )}
      </div>

      <Card className="gap-0 border-border py-0">
        <CardContent className="px-0 py-0">
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="w-16 text-muted-foreground">Rank</TableHead>
                <TableHead className="text-muted-foreground">Site</TableHead>
                <TableHead className="text-right text-muted-foreground">Reports</TableHead>
                <TableHead className="text-right text-muted-foreground">Flagged</TableHead>
                <TableHead className="text-right text-muted-foreground">Flag rate</TableHead>
                <TableHead className="text-right text-muted-foreground">Mean score</TableHead>
                <TableHead className="w-24 text-right text-muted-foreground">Δ rank</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow
                  key={r.key}
                  ref={setRowRef(r.key)}
                  className="border-border hover:bg-muted/40"
                >
                  <TableCell className="font-mono font-semibold text-foreground">
                    #{r.rank}
                  </TableCell>
                  <TableCell className="font-medium text-foreground">{r.key}</TableCell>
                  <TableCell className="text-right font-mono">{r.n_reports}</TableCell>
                  <TableCell className="text-right font-mono">{r.n_flagged}</TableCell>
                  <TableCell className="text-right font-mono">
                    {(r.sif_rate * 100).toFixed(1)}
                    <span className="ml-1 text-muted-foreground">per 100</span>
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {r.mean_score.toFixed(2)}
                  </TableCell>
                  <TableCell className="text-right">
                    <RankDelta delta={r.prev_rank - r.rank} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
