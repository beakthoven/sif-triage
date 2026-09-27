import * as React from "react"
import { Tabs as TabsPrimitive } from "radix-ui"
import { cn } from "@/lib/utils"

export type TabItem = {
  value: string
  label: React.ReactNode
  icon?: React.ReactNode
  badge?: React.ReactNode
}

type TabsProps = {
  items: TabItem[]
  value: string
  onChange: (value: string) => void
  /** underline = section tabs; segmented = mode switch inside a card. */
  variant?: "underline" | "segmented"
  className?: string
}

/**
 * Tab list only — the parent switches content in response to `onChange`.
 * Built on Radix Tabs, which provides roving tabindex, Left/Right arrow
 * navigation, Home/End jumps and `aria-selected` on the active trigger.
 * Active state: 2px orange indicator (DESIGN §5.7), never a hue-only fill.
 */
function Tabs({ items, value, onChange, variant = "underline", className }: TabsProps) {
  const segmented = variant === "segmented"
  return (
    <TabsPrimitive.Root value={value} onValueChange={onChange} className={cn("flex w-full min-w-0 flex-col", className)}>
      <TabsPrimitive.List
        className={cn(
          "flex min-w-full items-center",
          segmented
            ? "gap-1 rounded-md border border-border-subtle bg-surface-sunken p-1"
            : "gap-6 overflow-x-auto border-b border-border-subtle",
        )}
      >
        {items.map((item) => (
          <TabsPrimitive.Trigger
            key={item.value}
            value={item.value}
            className={cn(
              "group/tab relative inline-flex min-h-11 shrink-0 items-center justify-center gap-2 text-sm font-semibold whitespace-nowrap text-content-secondary transition-colors duration-150 ease-standard hover:text-content-primary data-[state=active]:text-content-primary",
              segmented
              ? "min-w-0 flex-1 rounded-md px-2 py-2 whitespace-normal sm:px-4 data-[state=active]:bg-surface-card data-[state=active]:shadow-sm"
              : "-mb-px border-b-2 border-transparent px-1 data-[state=active]:border-action-primary",
            )}
          >
            {item.icon != null && <span aria-hidden="true" className="[&_svg]:size-4">{item.icon}</span>}
            {item.label}
            {item.badge != null && (
              <span className="rounded-full bg-surface-sunken px-2 font-mono text-xs text-content-secondary group-data-[state=active]/tab:bg-action-secondary">
                {item.badge}
              </span>
            )}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
    </TabsPrimitive.Root>
  )
}

export { Tabs }
