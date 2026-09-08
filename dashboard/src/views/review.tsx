import { GrayStateCard } from "@/components/gray-state-card";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { OVERRIDES } from "@/lib/mock";
import { t, type Lang } from "@/lib/phrasebook";
import type { Report } from "@/lib/types";

/** Review: override queue. Section 1 — gated reports awaiting HSE disposition.
 *  Section 2 — logged overrides (→ future gold labels; export path exists
 *  server-side as GET /overrides/export.csv). */
export function ReviewView({
  gatedReports,
  lang,
}: {
  gatedReports: Report[];
  lang: Lang;
}) {
  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 text-xl font-semibold text-foreground">
          {t(lang, "awaiting")}{" "}
          <span className="font-mono text-sm text-muted-foreground">
            ({gatedReports.length})
          </span>
        </h2>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {gatedReports.map((r) =>
            r.prediction.gates.map((g) => (
              <GrayStateCard key={`${r.id}-${g}`} report={r} gate={g} />
            )),
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xl font-semibold text-foreground">
          {t(lang, "overrides")}{" "}
          <span className="ml-2 font-mono text-sm font-normal text-muted-foreground">
            overrides → future gold labels
          </span>
        </h2>
        <Card className="border-border py-0">
          <CardContent className="px-0 py-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground">Report</TableHead>
                  <TableHead className="text-muted-foreground">Field</TableHead>
                  <TableHead className="text-muted-foreground">Old</TableHead>
                  <TableHead className="text-muted-foreground">New</TableHead>
                  <TableHead className="text-muted-foreground">Labeler</TableHead>
                  <TableHead className="text-right text-muted-foreground">Timestamp</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {OVERRIDES.map((o, i) => (
                  <TableRow key={i} className="border-border hover:bg-muted/40">
                    <TableCell className="font-mono">{o.report_id}</TableCell>
                    <TableCell className="font-mono">{o.field}</TableCell>
                    <TableCell className="font-mono text-muted-foreground line-through">
                      {o.old_value}
                    </TableCell>
                    <TableCell className="font-mono font-semibold text-primary">
                      {o.new_value}
                    </TableCell>
                    <TableCell className="font-mono text-muted-foreground">{o.labeler}</TableCell>
                    <TableCell className="text-right font-mono text-muted-foreground">
                      {new Date(o.ts).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
