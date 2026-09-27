import * as React from "react"
import { Popover as PopoverPrimitive } from "radix-ui"
import { DayPicker, type DateRange } from "react-day-picker"
import { hi } from "react-day-picker/locale/hi"
import { CalendarRange, ChevronDown } from "lucide-react"
import { formatLocalDate } from "@/lib/format"
import { t, type Lang } from "@/lib/phrasebook"
import { cn } from "@/lib/utils"
import "react-day-picker/style.css"

export type DateRangeValue = DateRange

// Bounds the demo register's observed date range (2024-01-02 through 2026-09-24).
export const DATA_WINDOW_START = new Date(2024, 0, 2)
export const DATA_WINDOW_END = new Date(2026, 8, 24)

function formatRange(value: DateRange | undefined, lang: Lang, emptyLabel: string): string {
  if (value?.from == null) return emptyLabel
  if (value.to == null) return formatLocalDate(value.from, lang)
  if (value.from.toDateString() === value.to.toDateString()) return formatLocalDate(value.from, lang)
  return `${formatLocalDate(value.from, lang)} – ${formatLocalDate(value.to, lang)}`
}

type DateRangePickerProps = {
  value?: DateRange
  onChange: (value: DateRange | undefined) => void
  className?: string
  lang?: Lang
  emptyLabel?: string
  ariaLabel?: string
}

/**
 * Incident-window filter wrapping react-day-picker in `mode="range"`.
 * Emits the full range on completion; `undefined` clears the filter.
 * The calendar's own CSS is re-skinned onto the token set via its
 * `--rdp-*` variables (no hex values here).
 */
function DateRangePicker({
  value,
  onChange,
  className,
  lang = "en",
  emptyLabel = "All dates",
  ariaLabel = "Select date range",
}: DateRangePickerProps) {
  const [open, setOpen] = React.useState(false)
  const complete = value?.from != null && value?.to != null

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          className={cn(
            "inline-flex h-11 min-w-0 items-center gap-2 rounded-md border border-border-default bg-surface-card px-3 text-sm font-medium text-content-primary outline-none transition-colors duration-150 hover:border-border-strong focus-visible:border-action-secondary-fg aria-expanded:border-action-secondary-fg",
            className,
          )}
        >
          <CalendarRange aria-hidden="true" className="size-4 shrink-0 text-content-secondary" />
          <span className="truncate">{formatRange(value, lang, emptyLabel)}</span>
          <ChevronDown aria-hidden="true" className="ml-auto size-4 shrink-0 text-content-muted" />
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="end"
          sideOffset={6}
          collisionPadding={8}
          className="z-50 max-h-[var(--radix-popover-content-available-height)] max-w-[calc(100vw-16px)] overflow-auto overscroll-contain rounded-lg border border-border-subtle bg-surface-raised p-2 shadow-lg outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 sm:p-3"
        >
          <DayPicker
            mode="range"
            locale={lang === "hi" ? hi : undefined}
            selected={value}
            numberOfMonths={2}
            style={
              {
                "--rdp-accent-color": "var(--action-primary)",
                "--rdp-accent-background-color": "var(--action-secondary)",
                "--rdp-range_start-color": "var(--action-primary-fg)",
                "--rdp-range_end-color": "var(--action-primary-fg)",
                "--rdp-range_middle-color": "var(--content-primary)",
                "--rdp-today-color": "var(--content-link)",
                "--rdp-day-width": "min(44px, calc((100vw - 40px) / 7))",
                "--rdp-day_button-width": "min(42px, calc((100vw - 40px) / 7 - 2px))",
                "--rdp-nav_button-height": "44px",
                "--rdp-nav_button-width": "44px",
              } as React.CSSProperties
            }
            startMonth={DATA_WINDOW_START}
            endMonth={DATA_WINDOW_END}
            onSelect={(range) => {
              onChange(range ?? undefined)
              if (range?.from != null && range?.to != null) setOpen(false)
            }}
            footer={null}
          />
          {complete && (
            <div className="mt-2 border-t border-border-subtle pt-2 text-right">
              <button
                type="button"
                onClick={() => {
                  onChange(undefined)
                  setOpen(false)
                }}
                className="min-h-11 rounded-sm px-3 text-sm font-medium text-content-link outline-none transition-colors hover:bg-action-ghost-hover"
              >
                {t(lang, "clearDates")}
              </button>
            </div>
          )}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}

export { DateRangePicker }