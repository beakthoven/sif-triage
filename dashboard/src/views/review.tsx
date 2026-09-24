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
import type { OverrideOut } from "@/lib/types";

function humanize(value: string | null): string {
  if (!value) return "Not recorded";
  const labels: Record<string, string> = {
    sif_label: "SIF assessment",
    sif_potential: "SIF-potential",
    not_sif_potential: "Not SIF-potential",
    HIGH: "High priority",
    MODERATE: "Moderate priority",
    LOW: "Low priority",
    hse_reviewer: "HSE reviewer",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

/** Review: override queue. Section 1 — gated reports awaiting the HSE
 *  reviewer (gates route here, never auto-clear). Section 2 — logged
 *  overrides (GET /api/review; → future gold labels, source column
 *  separates "override" from "blind_gold"). */
export function ReviewView({
  overrides,
  lang,
}: {
  overrides: OverrideOut[];
  lang: Lang;
}) {
  return (
    <section aria-label={t(lang, "tabHistory")} className="space-y-6">
      {overrides.length === 0 ? (
        <Card className="border-dashed border-border bg-transparent">
          <CardContent className="items-center px-6 py-12 text-center">
            <h3 className="text-lg font-semibold text-foreground">{t(lang, "noDecisions")}</h3>
            <p className="max-w-md text-muted-foreground">
              {t(lang, "noDecisionsBody")}
            </p>
          </CardContent>
        </Card>
      ) : (
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
                    <TableCell>{humanize(o.field)}</TableCell>
                    <TableCell className="text-muted-foreground line-through">
                      {humanize(o.old_value)}
                    </TableCell>
                    <TableCell className="font-semibold text-foreground">
                      {humanize(o.new_value)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{humanize(o.labeler)}</TableCell>
                    <TableCell className="text-right font-mono text-muted-foreground">
                      {new Date(o.ts).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </section>
  );
}
