import * as React from "react"
import { motion } from "motion/react"
import { cn } from "@/lib/utils"

export type ProgressProps = {
  value?: number
  max?: number
  label?: React.ReactNode
  detail?: React.ReactNode
  indeterminate?: boolean
  className?: string
}

/**
 * Determinate by default (`value` / `max`). `indeterminate` renders a
 * sweeping bar for stages with no known total — announced to assistive tech
 * via `role="progressbar"` with no `aria-valuenow`; the sweep is disabled for
 * reduced-motion users (`MotionConfig reducedMotion="user"`). Steel blue, not
 * orange: progress is state, not an action.
 */
function Progress({ value, max = 100, label, detail, indeterminate = false, className }: ProgressProps) {
  const pct =
    !indeterminate && value != null && max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : null

  return (
    <div className={cn("flex w-full min-w-0 flex-col gap-2", className)}>
      {(label != null || detail != null) && (
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <span className="text-sm font-semibold text-content-primary">{label}</span>
          {detail != null && <span className="font-mono text-xs text-content-secondary">{detail}</span>}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={pct == null ? undefined : Math.round(pct)}
        aria-label={typeof label === "string" ? label : undefined}
        className="h-2 w-full overflow-hidden rounded-full bg-surface-sunken"
      >
        {indeterminate ? (
          <motion.div
            className="h-full w-1/3 rounded-full bg-action-secondary-fg"
            animate={{ x: ["-100%", "300%"] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: [0.2, 0, 0, 1] }}
          />
        ) : (
          <div
            className="h-full rounded-full bg-action-secondary-fg transition-[width] duration-220 ease-standard"
            style={{ width: `${pct ?? 0}%` }}
          />
        )}
      </div>
    </div>
  )
}

export { Progress }
