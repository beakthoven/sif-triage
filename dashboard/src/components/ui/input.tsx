import * as React from "react"
import { cn } from "@/lib/utils"

/* DESIGN §5.2: 44px minimum height, 1px border, radius-md; focus turns the
 * border steel blue AND adds the global 2px orange ring (never border alone). */
const baseStyles =
  "w-full min-w-0 rounded-md border border-border-default bg-surface-card text-content-primary transition-[border-color,box-shadow] duration-150 ease-standard placeholder:text-content-muted hover:border-border-strong focus-visible:border-action-secondary-fg aria-invalid:border-status-danger-fill disabled:cursor-not-allowed disabled:bg-action-disabled disabled:text-action-disabled-fg"

const sizeStyles = {
  sm: "h-11 px-3 text-base md:text-sm",
  md: "h-11 px-4 text-base",
} as const

type InputProps = Omit<React.ComponentProps<"input">, "size"> & {
  size?: keyof typeof sizeStyles
  invalid?: boolean
}

function Input({ className, size = "md", invalid = false, ...props }: InputProps) {
  return (
    <input
      type="text"
      data-size={size}
      aria-invalid={invalid || undefined}
      className={cn(baseStyles, sizeStyles[size], className)}
      {...props}
    />
  )
}

type TextareaProps = React.ComponentProps<"textarea"> & {
  rows?: number
  invalid?: boolean
}

function Textarea({ className, rows = 4, invalid = false, ...props }: TextareaProps) {
  return (
    <textarea
      rows={rows}
      aria-invalid={invalid || undefined}
      className={cn(baseStyles, "resize-y px-4 py-3 text-base", className)}
      {...props}
    />
  )
}

export { Input, Textarea }
