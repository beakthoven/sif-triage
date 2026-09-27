/* The queue grid: @tanstack/react-table v9 (columns + sorted row model) over
 * @tanstack/react-virtual (fixed-height windowed rows). Rendered as an ARIA
 * grid of divs because a real <table> tbody cannot be virtualized reliably.
 * Keyboard-first: the scroll container holds focus (aria-activedescendant
 * pattern) — j/k or arrows move, x toggles bulk selection, Enter opens. */

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import {
  createColumnHelper,
  createSortedRowModel,
  flexRender,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronDown, ChevronRight, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { Chip } from "@/components/ui";
import { formatDisplayDate } from "@/lib/format";
import { gateCopyFor, t as tShared, type Lang } from "@/lib/phrasebook";
import { tq } from "./strings";
import type { ClusterOut } from "@/lib/types";
import type { QueueRow } from "./api";

const ROW_H = 76;
const GRID_COLS =
  "32px 60px minmax(220px,1.7fr) minmax(154px,0.9fr) 92px 104px 148px";

/* Verdict tone + word per the design spec verdict table (words carried by the
 * shell phrasebook's bandHigh/bandModerate/bandLow). The word is always the
 * chip's content, never hue alone. */
const BAND_TONE = { HIGH: "high", MODERATE: "moderate", LOW: "low" } as const;
const BAND_WORD_KEY = {
  HIGH: "bandHigh",
  MODERATE: "bandModerate",
  LOW: "bandLow",
} as const;

const COMPACT_GATE_LABELS: Record<string, { en: string; hi: string }> = {
  min_length: { en: "Short report", hi: "छोटी रिपोर्ट" },
  negation: { en: "Negation", hi: "नकारात्मक वाक्य" },
  language: { en: "Language review", hi: "भाषा समीक्षा" },
  confidence: { en: "Uncertain score", hi: "अनिश्चित स्कोर" },
  drill: { en: "Drill / test", hi: "ड्रिल / परीक्षण" },
  near_dup: { en: "Training match", hi: "प्रशिक्षण मेल" },
  long_input: { en: "Section scored", hi: "खंड स्कोर" },
  well_control_watch: { en: "Well control", hi: "वेल कंट्रोल" },
  chunked_low_score: { en: "Section uncertainty", hi: "खंड अनिश्चितता" },
  severity_watch: { en: "Serious language", hi: "गंभीर भाषा" },
  verdict_stability: { en: "Unstable verdict", hi: "अस्थिर निर्णय" },
  energy_isolation_absent: { en: "Energy isolation", hi: "ऊर्जा अवरोधन" },
  gas_test_absent: { en: "Gas test", hi: "गैस टेस्ट" },
  permit_absent: { en: "Permit to work", hi: "वर्क परमिट" },
  fire_watch_absent: { en: "Fire watch", hi: "फायर वॉच" },
  standby_absent: { en: "Standby man", hi: "स्टैंडबाय व्यक्ति" },
  atmosphere_unmonitored: { en: "Atmosphere", hi: "वातावरण निगरानी" },
};

function compactGateLabel(lang: Lang, name: string): string {
  const compact = COMPACT_GATE_LABELS[name];
  return compact ? compact[lang] : gateCopyFor(lang, name).name;
}

export interface QueueTableProps {
  rows: QueueRow[];
  groups: { cluster: ClusterOut; visibleRows: QueueRow[]; representative: QueueRow }[];
  sorting: SortingState;
  selection: Set<number>;
  onToggleRow: (id: number) => void;
  onToggleAll: () => void;
  allSelected: boolean;
  someSelected: boolean;
  selectedId: number | null;
  onSelectReport: (id: number) => void;
  onOpenReport?: (id: number) => void;
  lang: Lang;
}

const FEATURES = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
});
const helper = createColumnHelper<typeof FEATURES, QueueRow>();

export function QueueTable(props: QueueTableProps) {
  const { rows, sorting, selection, lang } = props;
  const scrollRef = useRef<HTMLDivElement>(null);
  const [cursor, setCursor] = useState(0);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const groupsByMember = useMemo(() => {
    const byMember = new Map<number, (typeof props.groups)[number]>();
    for (const group of props.groups) {
      for (const member of group.visibleRows) byMember.set(member.id, group);
    }
    return byMember;
  }, [props.groups]);

  const columns = useMemo(
    () =>
      helper.columns([
        helper.display({
          id: "select",
          header: () => (
            <input
              type="checkbox"
              aria-label={tq(lang, "selectAll")}
              checked={props.allSelected}
              ref={(el) => {
                if (el) el.indeterminate = props.someSelected && !props.allSelected;
              }}
              onChange={props.onToggleAll}
              onClick={(e) => e.stopPropagation()}
              className="size-4 cursor-pointer accent-action-primary"
            />
          ),
          cell: ({ row }) => (
            <input
              type="checkbox"
              aria-label={`${tq(lang, "selectReport")} #${row.original.id}`}
              checked={selection.has(row.original.id)}
              onChange={() => props.onToggleRow(row.original.id)}
              onClick={(e) => e.stopPropagation()}
              className="size-4 cursor-pointer accent-action-primary"
            />
          ),
        }),
        helper.accessor("id", {
          header: () => "ID",
          cell: ({ row }) => (
            <span className="font-mono text-xs leading-5 text-content-secondary">
              #{row.original.id}
            </span>
          ),
        }),
        helper.accessor((r) => r.text, {
          id: "report",
          header: () => tShared(lang, "colReport"),
          cell: ({ row }) => (
            <span className="flex min-w-0 flex-col gap-0.5" title={row.original.text}>
              <span className="line-clamp-2 leading-5 text-content-primary">
                {row.original.text}
              </span>
            </span>
          ),
        }),
        helper.accessor((r) => `${r.site ?? ""} ${r.activity ?? ""} ${r.contractor ?? ""}`, {
          id: "context",
          header: () => tq(lang, "colContext"),
          cell: ({ row }) => {
            const facets = [
              { label: tShared(lang, "site"), value: row.original.site },
              { label: tq(lang, "colActivity"), value: row.original.activity },
              { label: tq(lang, "colContractor"), value: row.original.contractor },
            ].filter((facet) => facet.value);

            if (facets.length === 0) {
              return <span className="font-mono text-xs text-content-muted">—</span>;
            }

            return (
              <span
                className="flex min-w-0 flex-col gap-0.5 text-[11px] leading-3.5 text-content-secondary"
                title={facets.map((facet) => `${facet.label}: ${facet.value}`).join(" · ")}
              >
                {facets.map((facet) => (
                  <span key={facet.label} className="block truncate">
                    <span className="text-content-muted">{facet.label}:</span>{" "}
                    {facet.value}
                  </span>
                ))}
              </span>
            );
          },
        }),
        helper.accessor((r) => r.displayDate, {
          id: "date",
          header: () => tq(lang, "colDate"),
          cell: ({ row }) => (
            <span className="font-mono text-xs leading-5 whitespace-nowrap text-content-secondary">
              {formatDisplayDate(row.original.displayDate, lang)}
              {row.original.dateIsIngested && (
                <span title={tq(lang, "ingestLegend")} className="text-content-muted">
                  *
                </span>
              )}
            </span>
          ),
        }),
        helper.accessor((r) => r.score ?? -1, {
          id: "score",
          header: () => tq(lang, "colPriority"),
          cell: ({ row }) =>
            row.original.score !== null ? (
              <span className="flex min-w-0 flex-col items-start gap-1">
                {row.original.band !== null ? (
                  <Chip tone={BAND_TONE[row.original.band]} size="sm">
                    {tShared(lang, BAND_WORD_KEY[row.original.band])}
                  </Chip>
                ) : (
                  <Chip tone="neutral" size="sm" title={tq(lang, "bandAbsentDetail")}>
                    {tq(lang, "verdictUnbanded")}
                  </Chip>
                )}
                <span className="font-mono text-[11px] leading-3 tabular-nums text-content-muted">
                  {tq(lang, "scoreShort")} {row.original.score.toFixed(2)}
                </span>
              </span>
            ) : (
              <Chip tone="neutral" size="sm">{tq(lang, "unscored")}</Chip>
            ),
        }),
        helper.accessor((r) => r.grayGates.length, {
          id: "flags",
          header: () => tq(lang, "colFlags"),
          cell: ({ row }) => {
            const r = row.original;
            const gateSummary = r.grayGates.map((gate) => compactGateLabel(lang, gate.name));
            const flagCount = r.grayGates.length + (r.nearDup ? 1 : 0);

            if (flagCount === 0) {
              return <span className="text-xs text-content-muted">{tq(lang, "noFlags")}</span>;
            }

            if (r.grayGates.length > 0) {
              const primaryGate = r.grayGates[0];
              const secondaryFlags = [
                ...gateSummary.slice(1),
                ...(r.nearDup ? [tq(lang, "duplicateFlag")] : []),
              ];
              return (
                <span className="flex min-w-0 flex-col items-start gap-1">
                  <span
                    className="max-w-full rounded-md bg-verdict-uncertain-chip px-2 py-1 text-[11px] leading-3.5 font-semibold whitespace-normal text-verdict-uncertain"
                    title={r.grayGates.map((g) => gateCopyFor(lang, g.name).sentence).join(" ")}
                  >
                    {compactGateLabel(lang, primaryGate.name)}
                  </span>
                  {secondaryFlags.length > 0 && (
                    <span
                      className="line-clamp-2 text-[10px] leading-3 text-content-muted"
                      title={secondaryFlags.join(" · ")}
                    >
                      {secondaryFlags.join(" · ")}
                    </span>
                  )}
                </span>
              );
            }

            return (
              <Chip
                tone="neutral"
                size="sm"
                icon={<Copy aria-hidden="true" />}
                title={tShared(lang, "possibleDuplicate")}
                aria-label={tShared(lang, "possibleDuplicate")}
              >
                {tq(lang, "duplicateFlag")}
              </Chip>
            );
          },
        }),
      ]),
    // The cells close over live selection/toggle handlers, so the defs
    // rebuild when they change. Data flows through table options, not defs.
    [lang, selection, props.allSelected, props.someSelected, props.onToggleAll, props.onToggleRow],
  );

  const table = useTable({
    features: FEATURES,
    columns,
    data: rows,
    state: { sorting },
    // The toolbar owns the sort (URL state); the table never initiates one.
    onSortingChange: () => {},
  });
  const tableRows = table.getRowModel().rows;
  const displayRows = useMemo(() => {
    const tableRowsById = new Map(tableRows.map((row) => [row.original.id, row]));
    return tableRows.flatMap((row) => {
      const group = groupsByMember.get(row.original.id);
      const isLead = group?.representative.id === row.original.id;
      if (group && !isLead) return [];
      const entries: { row: (typeof tableRows)[number]; group: (typeof props.groups)[number] | undefined; isMember: boolean; parentId: number; key: string }[] = [
        { row, group, isMember: false, parentId: row.original.id, key: `lead-${row.original.id}` },
      ];
      if (group && isLead && expanded.has(row.original.id)) {
        for (const member of group.visibleRows) {
          if (member.id === row.original.id) continue;
          const memberRow = tableRowsById.get(member.id);
          if (memberRow) entries.push({ row: memberRow, group, isMember: true, parentId: row.original.id, key: `member-${member.id}` });
        }
      }
      return entries;
    });
  }, [tableRows, groupsByMember, expanded]);

  const virtualizer = useVirtualizer({
    count: displayRows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_H,
    overscan: 12,
  });

  useEffect(() => {
    setCursor((c) => Math.min(c, Math.max(0, displayRows.length - 1)));
  }, [displayRows.length]);

  const moveCursor = (next: number) => {
    if (displayRows.length === 0) return;
    const clamped = Math.min(Math.max(next, 0), displayRows.length - 1);
    setCursor(clamped);
    virtualizer.scrollToIndex(clamped, { align: "auto" });
  };

  const onKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    // Keys act only when the grid itself holds focus (activedescendant
    // pattern); inner controls handle their own keys.
    if (e.target !== e.currentTarget) return;
    const row = displayRows[cursor]?.row.original ?? null;
    switch (e.key) {
      case "j":
      case "ArrowDown":
        e.preventDefault();
        moveCursor(cursor + 1);
        break;
      case "k":
      case "ArrowUp":
        e.preventDefault();
        moveCursor(cursor - 1);
        break;
      case "Home":
        e.preventDefault();
        moveCursor(0);
        break;
      case "End":
        e.preventDefault();
        moveCursor(displayRows.length - 1);
        break;
      case "x":
        e.preventDefault();
        if (row) props.onToggleRow(row.id);
        break;
      case "Enter":
        e.preventDefault();
        if (!row) break;
        if (props.onOpenReport) props.onOpenReport(row.id);
        else props.onSelectReport(row.id);
        break;
      default:
        break;
    }
  };

  return (
    <div
      ref={scrollRef}
      role="grid"
      aria-label={tq(lang, "gridLabel")}
      aria-rowcount={displayRows.length + 1}
      aria-activedescendant={displayRows[cursor] ? `qrow-${displayRows[cursor].row.original.id}` : undefined}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="group/grid h-[min(72vh,720px)] min-w-0 overflow-y-auto overflow-x-hidden rounded-lg border border-border-default bg-surface-card shadow-[inset_0_1px_0_color-mix(in_srgb,var(--content-primary)_4%,transparent)]"
    >
      <div className="sticky top-0 z-10 border-b border-border-default bg-surface-canvas">
        <div
          role="row"
          aria-rowindex={1}
          className="grid h-12 items-center gap-2 px-3 text-[11px] font-semibold tracking-[0.04em] text-content-secondary uppercase"
          style={{ gridTemplateColumns: GRID_COLS }}
        >
          {table.getHeaderGroups()[0]?.headers.map((header, hi) => (
            <div key={header.id} role="columnheader" aria-colindex={hi + 1} className="truncate">
              {header.isPlaceholder
                ? null
                : flexRender(header.column.columnDef.header, header.getContext())}
            </div>
          ))}
        </div>
      </div>
      <div className="relative" style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((vItem) => {
          const entry = displayRows[vItem.index];
          const r = entry.row.original;
          const groupLead = !entry.isMember;
          const checked = selection.has(r.id);
          const filteredClusterMembers = entry.group
            ? entry.group.cluster.n > entry.group.visibleRows.length
            : false;
          const isExpanded = entry.group ? expanded.has(entry.parentId) : false;
          return (
            <div
              key={entry.key}
              role="row"
              id={`qrow-${r.id}`}
              aria-rowindex={vItem.index + 2}
              aria-selected={checked}
              aria-current={props.selectedId === r.id || undefined}
              onClick={() => {
                setCursor(vItem.index);
                props.onSelectReport(r.id);
              }}
              onDoubleClick={() => props.onOpenReport?.(r.id)}
              className={cn(
                "grid cursor-pointer items-center gap-2 border-b border-border-subtle px-3 text-sm transition-colors duration-150 hover:bg-surface-sunken",
                entry.isMember
                  ? "border-l-2 border-l-action-primary/35 bg-surface-zebra pl-5 text-[13px]"
                  : vItem.index % 2 === 1 ? "bg-surface-zebra" : "bg-surface-card",
                checked && "bg-action-secondary",
                props.selectedId === r.id &&
                  "bg-action-secondary shadow-[inset_3px_0_0_var(--action-primary)]",
                cursor === vItem.index &&
                  "group-focus-visible/grid:outline-2 group-focus-visible/grid:-outline-offset-2 group-focus-visible/grid:outline-ring-focus",
              )}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: ROW_H,
                transform: `translateY(${vItem.start}px)`,
                gridTemplateColumns: GRID_COLS,
              }}
            >
              {entry.isMember ? (
                <>
                  <div role="gridcell" aria-colindex={1} className="min-w-0">
                    <input
                      type="checkbox"
                      aria-label={`${tq(lang, "selectReport")} #${r.id}`}
                      checked={selection.has(r.id)}
                      onChange={() => props.onToggleRow(r.id)}
                      onClick={(event) => event.stopPropagation()}
                      className="size-4 cursor-pointer accent-action-primary"
                    />
                  </div>
                  <div role="gridcell" aria-colindex={2} className="truncate font-mono text-xs leading-5 text-content-secondary">#{r.id}</div>
                  <div role="gridcell" aria-colindex={3} className="min-w-0 overflow-hidden">
                    <a
                      href={`#/report/${r.id}`}
                      onClick={(event) => event.stopPropagation()}
                      className="line-clamp-2 text-content-link underline decoration-border-default underline-offset-2 hover:decoration-current focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-ring-focus"
                      title={r.text}
                    >{r.text}</a>
                  </div>
                  <div role="gridcell" aria-colindex={4} className="min-w-0 overflow-hidden text-[11px] text-content-secondary">
                    {[r.site, r.activity, r.contractor].filter(Boolean).join(" · ") || "—"}
                  </div>
                  <div role="gridcell" aria-colindex={5} className="truncate font-mono text-xs text-content-secondary">{formatDisplayDate(r.displayDate, lang)}</div>
                  <div role="gridcell" aria-colindex={6} className="min-w-0">
                    {r.score !== null ? <span className="flex flex-col items-start gap-1">{r.band ? <Chip tone={BAND_TONE[r.band]} size="sm">{tShared(lang, BAND_WORD_KEY[r.band])}</Chip> : <Chip tone="neutral" size="sm">{tq(lang, "verdictUnbanded")}</Chip>}<span className="font-mono text-[11px] text-content-muted">{tq(lang, "scoreShort")} {r.score.toFixed(2)}</span></span> : <Chip tone="neutral" size="sm">{tq(lang, "unscored")}</Chip>}
                  </div>
                  <div role="gridcell" aria-colindex={7} className="min-w-0 overflow-hidden">
                    {r.grayGates.length || r.nearDup ? <span className="flex flex-col items-start gap-1">{r.grayGates[0] ? <span className="rounded-md bg-verdict-uncertain-chip px-2 py-1 text-[11px] font-semibold text-verdict-uncertain" title={r.grayGates.map((gate) => gateCopyFor(lang, gate.name).sentence).join(" ")}>{compactGateLabel(lang, r.grayGates[0].name)}</span> : <Chip tone="neutral" size="sm">{tq(lang, "duplicateFlag")}</Chip>}{r.grayGates.length > 1 && <span className="line-clamp-2 text-[10px] text-content-muted">{r.grayGates.slice(1).map((gate) => compactGateLabel(lang, gate.name)).join(" · ")}</span>}</span> : <span className="text-xs text-content-muted">{tq(lang, "noFlags")}</span>}
                  </div>
                </>
              ) : entry.row.getAllCells().map((cell, ci) => (
                <div
                  key={cell.id}
                  role="gridcell"
                  aria-colindex={ci + 1}
                  className={cn(
                    "min-w-0",
                    ci === 2 || ci === 3 || ci === 6 ? "overflow-hidden" : "truncate",
                  )}
                >
                  {ci === 2 ? (
                    <span className="flex min-w-0 flex-col gap-1">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      {groupLead && entry.group && (
                        <button
                          type="button"
                          aria-expanded={isExpanded}
                          title={tq(lang, filteredClusterMembers ? "similarInViewTitle" : "similarAllTitle")}
                          onClick={(event) => {
                            event.stopPropagation();
                            setExpanded((current) => {
                              const next = new Set(current);
                              if (next.has(r.id)) next.delete(r.id);
                              else next.add(r.id);
                              return next;
                            });
                          }}
                          className="inline-flex min-h-7 w-fit items-center gap-1 rounded-sm text-left text-xs font-medium text-content-link hover:underline focus-visible:outline-2 focus-visible:outline-ring-focus"
                        >
                          {isExpanded ? <ChevronDown aria-hidden="true" className="size-3.5" /> : <ChevronRight aria-hidden="true" className="size-3.5" />}
                          {isExpanded ? tq(lang, "collapseSimilar") : tq(lang, "similarReports", {
                            n: entry.group.visibleRows.length - 1,
                            plural: lang === "en" && entry.group.visibleRows.length - 1 !== 1 ? "s" : "",
                          })}
                        </button>
                      )}
                    </span>
                  ) : flexRender(cell.column.columnDef.cell, cell.getContext())}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}