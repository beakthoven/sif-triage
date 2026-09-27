import * as React from "react"
import { Tooltip as TooltipPrimitive } from "radix-ui"
import { cn } from "@/lib/utils"

type TooltipProps = {
  content: React.ReactNode
  children: React.ReactNode
  side?: "top" | "right" | "bottom" | "left"
  className?: string
}

/**
 * DESIGN §5.10: 300ms hover delay (instant on keyboard focus — Radix),
 * deep-blue background, white text-xs, radius-sm, max 240px, arrow.
 * `children` must be a single element that accepts a ref. Tooltips are for
 * non-essential enrichment — anything a reviewer must see belongs in the layout.
 */
function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={300} skipDelayDuration={100}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={6}
            collisionPadding={8}
            className={cn(
              "z-50 max-w-[240px] rounded-sm border border-chrome-border bg-chrome-bg px-2 py-1 text-xs text-chrome-fg shadow-lg outline-none data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0 data-[state=delayed-open]:duration-220 data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
              className,
            )}
          >
            {content}
            <TooltipPrimitive.Arrow className="fill-chrome-bg" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  )
}

export { Tooltip }
