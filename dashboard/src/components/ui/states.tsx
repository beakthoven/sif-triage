import * as React from "react"
import { Inbox, OctagonAlert } from "lucide-react"
import { Button } from "./button"
import { useLang } from "@/lib/lang"
import { t } from "@/lib/phrasebook"
import { cn } from "@/lib/utils"

type EmptyStateProps = {
  title: React.ReactNode
  description?: React.ReactNode
  action?: React.ReactNode
  icon?: React.ReactNode
  className?: string
}

/** DESIGN §6.4: icon, one sentence on why it's empty, optional action. */
function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border-default bg-surface-card px-6 py-12 text-center",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="mb-2 grid size-12 place-items-center rounded-full bg-surface-sunken text-content-secondary [&_svg]:size-6"
      >
        {icon ?? <Inbox />}
      </span>
      <p className="text-lg font-semibold text-content-primary">{title}</p>
      {description != null && <p className="max-w-md text-sm text-content-secondary">{description}</p>}
      {action != null && <div className="mt-4">{action}</div>}
    </div>
  )
}

type ErrorStateProps = {
  title: React.ReactNode
  description?: React.ReactNode
  onRetry?: () => void
  className?: string
}

function ErrorState({ title, description, onRetry, className }: ErrorStateProps) {
  const { lang } = useLang()
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-md border border-border-subtle bg-surface-card px-6 py-12 text-center",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="mb-2 grid size-12 place-items-center rounded-full bg-verdict-high-chip text-status-danger [&_svg]:size-6"
      >
        <OctagonAlert />
      </span>
      <p className="text-lg font-semibold text-content-primary">{title}</p>
      {description != null && <p className="max-w-md text-sm text-content-secondary">{description}</p>}
      {onRetry != null && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
          {t(lang, "tryAgain")}
        </Button>
      )}
    </div>
  )
}

export { EmptyState, ErrorState }
