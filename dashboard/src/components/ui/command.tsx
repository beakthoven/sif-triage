import * as React from "react"
import { Command as CommandPrimitive } from "cmdk"
import { Dialog as DialogPrimitive } from "radix-ui"
import { Search } from "lucide-react"
import { cn } from "@/lib/utils"

export type CommandItemDef = {
  value: string
  label: React.ReactNode
  icon?: React.ReactNode
  shortcut?: string
  disabled?: boolean
  onSelect?: (value: string) => void
}

export type CommandGroupDef = {
  heading?: React.ReactNode
  items: CommandItemDef[]
}

type CommandProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  placeholder?: string
  groups: CommandGroupDef[]
  className?: string
}

/** cmdk palette in a Radix dialog: full keyboard model (arrows, Enter, Esc). */
function Command({ open, onOpenChange, placeholder, groups, className }: CommandProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-surface-overlay data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          aria-label="Command menu"
          className={cn(
            "fixed top-[12vh] left-1/2 z-50 w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-lg border border-border-subtle bg-surface-raised shadow-xl outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
            className,
          )}
        >
          <CommandPrimitive loop className="flex flex-col">
            <div className="flex items-center gap-2 border-b border-border-subtle px-3">
              <Search aria-hidden="true" className="size-4 shrink-0 text-content-muted" />
              <CommandPrimitive.Input
                placeholder={placeholder}
                className="h-11 w-full bg-transparent text-base leading-6 text-content-primary outline-none placeholder:text-content-muted"
              />
            </div>
            <CommandPrimitive.List className="max-h-80 overflow-y-auto overscroll-contain p-1.5">
              <CommandPrimitive.Empty className="px-3 py-6 text-center text-sm leading-5 text-content-secondary">
                No matching items
              </CommandPrimitive.Empty>
              {groups.map((group, groupIndex) => (
                <CommandPrimitive.Group
                  key={groupIndex}
                  value={`group-${groupIndex}`}
                  heading={group.heading}
                  className="[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:leading-4 [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-content-secondary"
                >
                  {group.items.map((item) => (
                    <CommandPrimitive.Item
                      key={item.value}
                      value={item.value}
                      disabled={item.disabled}
                      onSelect={() => item.onSelect?.(item.value)}
                      className="flex cursor-default items-center gap-2 rounded-sm px-2.5 py-2 text-sm leading-5 text-content-primary outline-none data-[selected=true]:bg-action-ghost-hover data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50"
                    >
                      {item.icon != null && <span aria-hidden="true" className="[&_svg]:size-4">{item.icon}</span>}
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {item.shortcut != null && (
                        <kbd className="shrink-0 rounded-xs border border-border-subtle bg-surface-sunken px-1.5 font-mono text-xs leading-4 text-content-secondary">
                          {item.shortcut}
                        </kbd>
                      )}
                    </CommandPrimitive.Item>
                  ))}
                </CommandPrimitive.Group>
              ))}
            </CommandPrimitive.List>
          </CommandPrimitive>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export { Command }