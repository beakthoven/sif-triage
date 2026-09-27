import * as React from "react"
import { cn } from "@/lib/utils"

type CardProps = React.ComponentProps<"div"> & {
  /** compact for queue surfaces, comfortable for detail/explanations. */
  density?: "compact" | "comfortable"
  /** Only clickable cards lift on hover (DESIGN §5.3 — no false affordance). */
  interactive?: boolean
}

function Card({ className, density = "comfortable", interactive = false, ...props }: CardProps) {
  return (
    <div
      data-density={density}
      data-interactive={interactive || undefined}
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-border-subtle bg-surface-card shadow-sm",
        density === "compact" ? "gap-4 p-4 md:p-5" : "gap-5 p-5 md:p-6",
        interactive &&
          "cursor-pointer transition-shadow duration-150 hover:shadow-md focus-within:shadow-md",
        className,
      )}
      {...props}
    />
  )
}

type CardHeaderProps = Omit<React.ComponentProps<"div">, "title"> & {
  title: React.ReactNode
  meta?: React.ReactNode
  actions?: React.ReactNode
  icon?: React.ReactNode
}

function CardHeader({ className, title, meta, actions, icon, ...props }: CardHeaderProps) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-4", className)} {...props}>
      <div className="flex min-w-0 max-w-full items-start gap-3">
        {icon != null && (
          <span
            aria-hidden="true"
            className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-md bg-action-secondary text-content-link [&_svg]:size-4"
          >
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-content-primary">{title}</h3>
          {meta != null && <div className="mt-1 text-sm text-content-secondary">{meta}</div>}
        </div>
      </div>
      {actions != null && <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

function CardGrid({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("grid content-start items-stretch gap-4 sm:grid-cols-2 lg:gap-6 xl:grid-cols-3", className)}
      {...props}
    />
  )
}

export { Card, CardHeader, CardGrid }
