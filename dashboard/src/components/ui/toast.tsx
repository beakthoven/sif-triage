import * as React from "react"
import { Toaster as SonnerToaster, toast as sonnerToast } from "sonner"

export type NotifyOptions = {
  description?: React.ReactNode
  duration?: number
}

/**
 * Semantic toast helper over sonner (DESIGN §5.11): top-right, 5 s for
 * informational toasts, errors stay until dismissed. The message text
 * carries the meaning; sonner's per-type icon + the tone edge reinforce it.
 *
 * Mount <Toaster /> once (app shell) for any of these to render.
 */
export const notify = {
  success: (message: React.ReactNode, options?: NotifyOptions) => sonnerToast.success(message, options),
  error: (message: React.ReactNode, options?: NotifyOptions) =>
    sonnerToast.error(message, { duration: Infinity, closeButton: true, ...options }),
  info: (message: React.ReactNode, options?: NotifyOptions) => sonnerToast.info(message, options),
}

const toastClassNames = {
  toast:
    "rounded-md border border-border-subtle border-l-4 bg-surface-raised text-content-primary shadow-lg data-[type=success]:border-l-verdict-clear-fill data-[type=error]:border-l-status-danger-fill data-[type=info]:border-l-verdict-uncertain-fill",
  description: "text-sm text-content-secondary",
  title: "text-sm font-semibold",
  actionButton: "rounded-sm bg-action-primary px-2 py-1 text-sm font-semibold text-action-primary-fg",
  cancelButton: "rounded-sm bg-action-secondary px-2 py-1 text-sm font-semibold text-content-primary",
}

type ToasterProps = React.ComponentProps<typeof SonnerToaster>

function Toaster(props: ToasterProps) {
  return (
    <SonnerToaster
      position="top-right"
      duration={5000}
      visibleToasts={3}
      gap={8}
      toastOptions={{ classNames: toastClassNames }}
      {...props}
    />
  )
}

export { Toaster }
