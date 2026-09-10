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
import { t, type Lang } from "@/lib/phrasebook";
import type { OverrideOut, Report } from "@/lib/types";

/** Review: override queue. Section 1 — gated reports awaiting the HSE
 *  reviewer (gates route here, never auto-clear). Section 2 — logged
 *  overrides (GET /api/review; → future gold labels, source column
 *  separates "override" from "blind_gold"). */
export function ReviewView({
  gatedReports,
  overrides,
  lang,
}: {
  gatedReports: Report[];
  overrides: OverrideOut[];
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
        {gatedReports.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Nothing waiting — every report cleared the review gates.
          </p>
        )}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {gatedReports.map((r) =>
            r.prediction.gate_states
              .filter((g) => g.triggered && g.action !== "badge")
              .map((g) => (
                <GrayStateCard key={`${r.id}-${g.name}`} report={r} gate={g} />
              )),
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xl font-semibold text-foreground">
          {t(lang, "overrides")}{" "}
          <span className="ml-2 text-sm font-normal text-muted-foreground">
            {t(lang, "overridesNote")}
          </span>
        </h2>
        <Card className="gap-0 border-border py-0">
          <CardContent className="px-0 py-0">
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground">{t(lang, "colReport")}</TableHead>
                  <TableHead className="text-muted-foreground">{t(lang, "colField")}</TableHead>
                  <TableHead className="text-muted-foreground">{t(lang, "colWas")}</TableHead>
                  <TableHead className="text-muted-foreground">{t(lang, "colNow")}</TableHead>
                  <TableHead className="text-muted-foreground">{t(lang, "colReviewer")}</TableHead>
                  <TableHead className="text-right text-muted-foreground">{t(lang, "colWhen")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {overrides.map((o) => (
                  <TableRow key={o.id} className="border-border hover:bg-muted/40">
                    <TableCell className="font-mono">#{o.report_id}</TableCell>
                    <TableCell className="font-mono">{o.field}</TableCell>
                    <TableCell className="font-mono text-muted-foreground line-through">
                      {o.old_value ?? "—"}
                    </TableCell>
                    <TableCell className="font-mono font-semibold text-foreground">
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
