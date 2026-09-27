import * as React from "react"
import { cn } from "@/lib/utils"

type PageHeaderProps = {
  eyebrow?: React.ReactNode
  title: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
  /** Row under the description (stat chips, disclosures). */
  children?: React.ReactNode
  className?: string
}

/** Page title and description with wrapping page actions. One per route. */
function PageHeader({ eyebrow, title, description, actions, children, className }: PageHeaderProps) {
  return (
    <header className={cn("flex flex-col gap-4", className)}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 max-w-3xl basis-full md:basis-auto">
          {eyebrow != null && <p className="eyebrow">{eyebrow}</p>}
          <h1 className="page-title">{title}</h1>
          {description != null && (
            <p className="mt-2 text-base text-content-secondary">{description}</p>
          )}
        </div>
        {actions != null && <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </header>
  )
}

export { PageHeader }
