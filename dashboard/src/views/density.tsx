import { useRef, useState } from "react";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
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
import { DENSITY_AFTER, DENSITY_BEFORE } from "@/lib/mock";
import { t, type Lang } from "@/lib/phrasebook";
import type { DensityRow } from "@/lib/types";
import { useFlip } from "@/lib/use-flip";
import { cn } from "@/lib/utils";

function RankDelta({ delta }: { delta: number }) {
  if (delta === 0)
    return (
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        <Minus className="size-4" aria-hidden /> 0
      </span>
    );
  const up = delta > 0;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-mono font-semibold",
        up ? "text-primary" : "text-muted-foreground",
      )}
    >
      {up ? <ArrowUp className="size-4" aria-hidden /> : <ArrowDown className="size-4" aria-hidden />}
      {up ? `▲${delta}` : `▼${Math.abs(delta)}`}
    </span>
  );
}

/** Density: ranked site × activity table. The demo beat — ingest progress
 *  (~2s shell stand-in for the ~10s live beat), then rows visibly re-sort
 *  with FLIP: "Baghjan EPS just climbed to #1." */
export function DensityView({ lang }: { lang: Lang }) {
  const [rows, setRows] = useState<DensityRow[]>(DENSITY_BEFORE);
  const [ingesting, setIngesting] = useState(false);
  const [progress, setProgress] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const setRowRef = useFlip(rows);

  const reranked = rows !== DENSITY_BEFORE;

  function simulateIngest() {
    if (ingesting) return;
    setIngesting(true);
    setProgress(0);
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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <Button
          size="lg"
          onClick={simulateIngest}
          disabled={ingesting}
          className="min-h-11 bg-primary font-semibold text-primary-foreground hover:bg-primary/90"
        >
          {ingesting ? t(lang, "ingesting") : t(lang, "rerank")}
        </Button>
        {(ingesting || progress > 0) && (
          <div
            role="progressbar"
            aria-valuenow={Math.round(progress)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-2 min-w-48 flex-1 overflow-hidden rounded-full bg-muted"
          >
            <div
              className="hazard-stripe-dense h-full transition-[width] duration-100"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
        {reranked && !ingesting && (
          <p className="font-mono text-sm text-primary">
            Baghjan EPS · Well servicing just climbed to #1.
          </p>
        )}
      </div>

      <Card className="border-border py-0">
        <CardContent className="px-0 py-0">
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="w-16 text-muted-foreground">Rank</TableHead>
                <TableHead className="text-muted-foreground">Site × Activity</TableHead>
                <TableHead className="text-right text-muted-foreground">Reports</TableHead>
                <TableHead className="text-right text-muted-foreground">Flagged</TableHead>
                <TableHead className="text-right text-muted-foreground">Flag rate</TableHead>
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
                  <TableCell className="font-mono text-lg font-bold text-primary">
                    #{r.rank}
                  </TableCell>
                  <TableCell className="font-medium text-foreground">{r.key}</TableCell>
                  <TableCell className="text-right font-mono">{r.n_reports}</TableCell>
                  <TableCell className="text-right font-mono">{r.n_flagged}</TableCell>
                  <TableCell className="text-right font-mono">
                    {(r.flag_rate * 100).toFixed(1)}
                    <span className="ml-1 text-muted-foreground">per 100</span>
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
