/* DECISIONS audit table — the full log: report snippet + id, field, was, now,
 * WHO (real reviewer identity from the row), WHEN (sortable), RATIONALE,
 * severity (sortable, from the linked report's band), CAPA closure state, and
 * the Correct/CAPA actions. Sorting is owned by the ui Table primitive
 * (uncontrolled) via column sortValue accessors. */
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Table } from "@/components/ui/table";
import type { Lang } from "@/lib/phrasebook";
import { formatDisplayDate } from "@/lib/format";
import { fmtWhen, dt } from "./strings";
import { bandRank, bandTone, bandWord, humanizeField, humanizeValue } from "./values";
import {
  capaAged,
  type AuditRow,
  type Capa,
  type CapaStore,
  type ReportMeta,
} from "./data";

export interface AuditTableProps {
  lang: Lang;
  rows: AuditRow[];
  metas: Record<number, ReportMeta | null>;
  capas: CapaStore;
  superseded: Set<number>;
  onCorrect: (row: AuditRow) => void;
  onCapa: (row: AuditRow) => void;
}

export function AuditTable({
  lang,
  rows,
  metas,
  capas,
  superseded,
  onCorrect,
  onCapa,
}: AuditTableProps) {
  if (rows.length === 0) {
    return (
      <div
        role="region"
        aria-label={dt(lang, "decTitle")}
        className="flex min-h-32 items-center justify-center border-t border-border-subtle px-4 py-8 text-sm text-content-secondary"
      >
        {dt(lang, "emptyTitle")}
      </div>
    );
  }
  return (
    <div
      role="region"
      aria-label={dt(lang, "decTitle")}
      tabIndex={0}
      className="w-full overflow-x-auto"
    >
      <Table
        density="compact"
        stickyHeader
        data={rows}
      columns={[
        {
          id: "report",
          header: dt(lang, "colReport"),
          width: "minmax(220px, 2.2fr)",
          cell: (row: AuditRow) => {
            const meta = metas[row.report_id];
            return (
              <div className="min-w-0">
                <p className="line-clamp-2 max-w-96 text-sm text-content-primary">
                  {meta ? meta.snippet : <span className="text-content-muted">{dt(lang, meta === undefined ? "loadingSnippet" : "snippetNone")}</span>}
                </p>
                <p className="mt-0.5 font-mono text-xs text-content-secondary">
                  #{row.report_id}
                  {meta ? ` · ${meta.site} · ${formatDisplayDate(meta.reportedAt, lang)}` : ""}
                </p>
              </div>
            );
          },
        },
        {
          id: "field",
          header: dt(lang, "colField"),
          cell: (row: AuditRow) => (
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
              {humanizeField(lang, row.field)}
              {superseded.has(row.id) && (
                <Chip tone="neutral" size="sm">
                  {dt(lang, "superseded")}
                </Chip>
              )}
            </span>
          ),
        },
        {
          id: "was",
          header: dt(lang, "colWas"),
          cell: (row: AuditRow) => (
            <span className="line-through text-content-secondary">
              {row.old_value ? humanizeValue(lang, row.old_value) : "—"}
            </span>
          ),
        },
        {
          id: "now",
          header: dt(lang, "colNow"),
          cell: (row: AuditRow) => (
            <span className="font-semibold whitespace-nowrap text-content-primary">
              {humanizeValue(lang, row.new_value)}
            </span>
          ),
        },
        {
          id: "severity",
          header: dt(lang, "colSeverity"),
          sortable: true,
          sortValue: (row: AuditRow) => {
            const band = metas[row.report_id]?.band ?? null;
            return band ? bandRank(band) : null;
          },
          cell: (row: AuditRow) => {
            const band = metas[row.report_id]?.band ?? null;
            return band ? (
              <Chip tone={bandTone(band)} size="sm">
                {bandWord(lang, band)}
              </Chip>
            ) : (
              <span className="text-content-muted" title={dt(lang, "bandUnknown")}>
                —
              </span>
            );
          },
        },
        {
          id: "reviewer",
          header: dt(lang, "colReviewer"),
          cell: (row: AuditRow) => (
            <span className="text-sm whitespace-nowrap text-content-secondary">{row.labeler}</span>
          ),
        },
        {
          id: "when",
          header: dt(lang, "colWhen"),
          sortable: true,
          sortValue: (row: AuditRow) => new Date(row.created_at).getTime(),
          cell: (row: AuditRow) => (
            <span className="font-mono text-xs whitespace-nowrap text-content-secondary">
              {fmtWhen(lang, row.created_at)}
            </span>
          ),
        },
        {
          id: "rationale",
          header: dt(lang, "colRationale"),
          width: "minmax(160px, 1.6fr)",
          cell: (row: AuditRow) =>
            row.rationale ? (
              <p className="line-clamp-2 max-w-72 text-sm text-content-primary" title={row.rationale}>
                {row.rationale}
              </p>
            ) : (
              <span className="text-sm text-content-muted">{dt(lang, "rationaleNone")}</span>
            ),
        },
        {
          id: "actions",
          header: dt(lang, "colActions"),
          align: "right" as const,
          cell: (row: AuditRow) => {
            const capa: Capa | undefined = capas[row.id];
            const aged = capa ? capaAged(capa, row.created_at, new Date()) : false;
            return (
              <div className="flex flex-col items-end gap-1">
                <div className="flex justify-end gap-1">
                  <Button variant="secondary" size="sm" onClick={() => onCorrect(row)}>
                    {dt(lang, "correct")}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => onCapa(row)}>
                    {dt(lang, "capaBtn")}
                  </Button>
                </div>
                {capa && (
                  <p className="font-mono text-xs text-content-secondary">
                    {capa.owner} · {dt(lang, "capaDue")} {capa.due}
                    {aged && (
                      <Chip tone="danger" size="sm">
                        {dt(lang, "overdue")}
                      </Chip>
                    )}
                  </p>
                )}
              </div>
            );
          },
        },
        ]}
      />
    </div>
  );
}
