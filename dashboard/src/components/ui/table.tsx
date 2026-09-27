import * as React from "react"
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Controlled single-column sort state. `undefined` = no active sort (rows
 * render in the given order). The owner of the state owns the sort intent;
 * when the active column declares `sortValue`, this component applies that
 * comparator itself so both controlled and uncontrolled use land in the same
 * order deterministically.
 */
export type TableSort = { id: string; desc: boolean } | undefined

export type ColumnDef<Row> = {
  id: string
  header: React.ReactNode
  cell: (row: Row) => React.ReactNode
  align?: "left" | "center" | "right"
  width?: string | number
  sortable?: boolean
  /**
   * Row value used by the built-in sort. Required only when the table should
   * sort its own `data`; omit when the parent orders rows itself (e.g. a
   * server-side risk-ordered sort) and this component only displays and
   * reports sort intent.
   */
  sortValue?: (row: Row) => string | number | null | undefined
}

export type TableProps<Row> = {
  columns: Array<ColumnDef<Row>>
  data: Row[]
  sort?: TableSort
  onSortChange?: (sort: TableSort) => void
  density?: "compact" | "comfortable"
  stickyHeader?: boolean
  className?: string
}

const alignClass = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
} as const

function compareValues(a: string | number | null | undefined, b: string | number | null | undefined): number {
  if (a == null && b == null) return 0
  if (a == null) return 1
  if (b == null) return -1
  if (typeof a === "number" && typeof b === "number") return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true })
}

function nextSort(current: TableSort, id: string): TableSort {
  if (current == null || current.id !== id) return { id, desc: false }
  if (!current.desc) return { id, desc: true }
  return undefined
}

function Table<Row>({
  columns,
  data,
  sort,
  onSortChange,
  density = "compact",
  stickyHeader = false,
  className,
}: TableProps<Row>) {
  const controlled = onSortChange !== undefined
  const [internalSort, setInternalSort] = React.useState<TableSort>(undefined)
  const activeSort = controlled ? sort : internalSort

  const sortedRows = React.useMemo(() => {
    if (!activeSort) return data
    const column = columns.find((entry) => entry.id === activeSort.id)
    if (!column?.sortValue) return data
    const keyed = data.map((row) => ({ row, value: column.sortValue!(row) }))
    // Array.prototype.sort is stable in ES2019+; nulls always sort last.
    keyed.sort((a, b) => {
      const result = compareValues(a.value, b.value)
      return activeSort.desc ? -result : result
    })
    return keyed.map((entry) => entry.row)
  }, [data, columns, activeSort])

  const handleSortClick = (column: ColumnDef<Row>) => {
    const next = nextSort(activeSort, column.id)
    if (controlled) onSortChange(next)
    else setInternalSort(next)
  }

  const headStyles = cn(
    "border-b border-border-default bg-surface-canvas text-sm font-semibold text-content-secondary",
    density === "compact" ? "h-10 px-3" : "h-12 px-4",
  )
  const cellStyles = cn(
    "text-sm",
    density === "compact" ? "h-12 px-3 py-2" : "h-14 px-4 py-3",
  )

  return (
    <table className={cn("w-full border-collapse text-left", className)}>
      <thead>
        <tr>
          {columns.map((column) => {
            const isSorted = activeSort != null && activeSort.id === column.id
            const ariaSort: "ascending" | "descending" | undefined = isSorted
              ? activeSort.desc
                ? "descending"
                : "ascending"
              : undefined
            return (
              <th
                key={column.id}
                scope="col"
                aria-sort={ariaSort}
                style={column.width !== undefined ? { width: column.width } : undefined}
                className={cn(
                  headStyles,
                  alignClass[column.align ?? "left"],
                  stickyHeader && "sticky top-0 z-10",
                )}
              >
                {column.sortable ? (
                  <button
                    type="button"
                    onClick={() => handleSortClick(column)}
                    className="inline-flex min-h-11 items-center gap-1 rounded-sm transition-colors hover:text-content-primary"
                  >
                    {column.header}
                    {isSorted ? (
                      activeSort.desc ? (
                        <ArrowDown aria-hidden="true" className="size-3.5" />
                      ) : (
                        <ArrowUp aria-hidden="true" className="size-3.5" />
                      )
                    ) : (
                      <ArrowUpDown aria-hidden="true" className="size-3.5 text-content-muted" />
                    )}
                  </button>
                ) : (
                  column.header
                )}
              </th>
            )
          })}
        </tr>
      </thead>
      <tbody>
        {sortedRows.map((row, index) => (
          <tr
            key={index}
            className="border-b border-border-subtle bg-surface-card transition-colors duration-150 even:bg-surface-zebra last:border-b-0 hover:bg-surface-sunken"
          >
            {columns.map((column) => (
              <td key={column.id} className={cn(cellStyles, alignClass[column.align ?? "left"])}>
                {column.cell(row)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export { Table }