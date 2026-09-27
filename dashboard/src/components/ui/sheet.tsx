import * as React from "react"
import { Dialog as DialogPrimitive } from "radix-ui"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

type SheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  side: "right" | "bottom"
  title: React.ReactNode
  children: React.ReactNode
  className?: string
  closeLabel?: string
  onCloseAutoFocus?: React.ComponentProps<typeof DialogPrimitive.Content>["onCloseAutoFocus"]
}

/** Edge-anchored panel (mobile navigation, report drawer). Slides in on
 *  motion-medium/decelerate, out on accelerate (DESIGN §7.3). */
function Sheet({ open, onOpenChange, side, title, children, className, closeLabel = "Close", onCloseAutoFocus }: SheetProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-surface-overlay data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:duration-320 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:duration-220" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          onCloseAutoFocus={onCloseAutoFocus}
          className={cn(
            "z-50 flex flex-col bg-surface-raised shadow-lg outline-none data-[state=open]:animate-in data-[state=open]:duration-320 data-[state=open]:ease-decelerate data-[state=closed]:animate-out data-[state=closed]:duration-220 data-[state=closed]:ease-accelerate",
            side === "right"
              ? "fixed top-0 right-0 h-dvh w-[min(400px,100vw)] border-l border-border-subtle data-[state=open]:slide-in-from-right data-[state=closed]:slide-out-to-right"
              : "fixed inset-x-0 bottom-0 max-h-[85dvh] rounded-t-lg border-t border-border-subtle data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
            className,
          )}
        >
          <div className="flex min-h-14 shrink-0 items-center justify-between gap-2 border-b border-border-subtle pr-2 pl-4">
            <DialogPrimitive.Title className="min-w-0 py-3 text-lg font-semibold text-content-primary">
              {title}
            </DialogPrimitive.Title>
            <DialogPrimitive.Close
              aria-label={closeLabel}
              className="grid size-11 shrink-0 place-items-center rounded-md text-content-secondary transition-colors duration-150 hover:bg-action-ghost-hover hover:text-content-primary"
            >
              <X aria-hidden="true" className="size-5" />
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 pb-[max(16px,env(safe-area-inset-bottom))]">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export { Sheet }
