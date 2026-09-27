import * as React from "react"
import { Dialog as DialogPrimitive } from "radix-ui"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

type DialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  description?: React.ReactNode
  footer?: React.ReactNode
  children: React.ReactNode
  /** form = 560px (default), content = 720px (DESIGN §5.9). */
  size?: "form" | "content"
  className?: string
  closeLabel?: string
}

/** DESIGN §5.9: centered, radius-lg, shadow-lg, blue scrim; visible close,
 *  Esc and scrim-click close; Radix traps focus and the opener regains it.
 *  Opens on motion-medium/decelerate, closes on accelerate. */
function Dialog({ open, onOpenChange, title, description, footer, children, size = "form", className, closeLabel = "Close" }: DialogProps) {
  const descriptionId = React.useId()
  const returnFocusRef = React.useRef<HTMLElement | null>(null)
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-surface-overlay data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:duration-320 data-[state=open]:ease-decelerate data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:duration-220 data-[state=closed]:ease-accelerate" />
        <DialogPrimitive.Content
          aria-describedby={description != null ? descriptionId : undefined}
          onOpenAutoFocus={() => {
            returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault()
            if (returnFocusRef.current?.isConnected) returnFocusRef.current.focus({ preventScroll: true })
          }}
          className={cn(
            "fixed top-1/2 left-1/2 z-50 flex max-h-[85dvh] w-[calc(100%-32px)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-lg border border-border-subtle bg-surface-raised shadow-lg outline-none",
            size === "content" ? "max-w-[720px]" : "max-w-[560px]",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-[0.97] data-[state=open]:duration-320 data-[state=open]:ease-decelerate",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-[0.97] data-[state=closed]:duration-220 data-[state=closed]:ease-accelerate",
            className,
          )}
        >
            <div className="flex shrink-0 flex-col gap-2 py-4 pr-16 pl-4 sm:py-6 sm:pl-6">
              <DialogPrimitive.Title className="break-words text-xl font-semibold text-content-primary">
                {title}
              </DialogPrimitive.Title>
              {description != null && (
                <DialogPrimitive.Description id={descriptionId} className="text-sm text-content-secondary">
                  {description}
                </DialogPrimitive.Description>
              )}
            </div>
            {children != null && <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-4 sm:px-6 sm:pb-6">{children}</div>}
            {footer != null && (
              <div className="flex shrink-0 flex-row-reverse flex-wrap items-center justify-start gap-2 border-t border-border-subtle px-4 py-4 sm:px-6">
                {footer}
              </div>
            )}
            <DialogPrimitive.Close
              aria-label={closeLabel}
              className="absolute top-4 right-4 grid size-11 place-items-center rounded-md text-content-secondary transition-colors duration-150 hover:bg-action-ghost-hover hover:text-content-primary"
            >
              <X aria-hidden="true" className="size-5" />
            </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export { Dialog }
