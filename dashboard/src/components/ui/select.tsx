import * as React from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

export type SelectOption = { value: string; label: React.ReactNode }

type SelectProps = Omit<React.ComponentProps<"select">, "value" | "onChange" | "size"> & {
  options: SelectOption[]
  value: string
  onChange: (value: string) => void
  size?: "sm" | "md"
  invalid?: boolean
}

/** Native `<select>` — keyboard + mobile behaviour for free, token-styled. */
function Select({ options, value, onChange, size = "md", invalid = false, className, ...props }: SelectProps) {
  return (
    <div className={cn("relative w-full min-w-0", className)}>
      <select
        data-size={size}
        aria-invalid={invalid || undefined}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={cn(
          "h-11 w-full min-w-0 cursor-pointer appearance-none rounded-md border border-border-default bg-surface-card pr-10 text-content-primary transition-[border-color] duration-150 ease-standard hover:border-border-strong focus-visible:border-action-secondary-fg aria-invalid:border-status-danger-fill disabled:cursor-not-allowed disabled:bg-action-disabled disabled:text-action-disabled-fg",
          size === "sm" ? "pl-3 text-base md:text-sm" : "pl-4 text-base",
        )}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-content-secondary"
      />
    </div>
  )
}

export { Select }
