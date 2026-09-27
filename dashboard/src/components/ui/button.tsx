import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { LoaderCircle } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * DESIGN §5.1. Primary = safety orange with graphite text (never white —
 * 2.85:1), one per screen. Secondary = steel-blue outline. Ghost = tertiary
 * text button, underline on hover. Every size keeps a ≥44px hit area; the
 * smaller visual sizes extend it with an invisible ::after.
 */
const buttonVariants = cva(
  [
    "relative inline-flex shrink-0 select-none items-center justify-center gap-2 rounded-md font-semibold whitespace-nowrap",
    "transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-standard",
    "active:scale-[0.98] active:duration-50",
    "disabled:cursor-not-allowed disabled:active:scale-100",
    "[&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:pointer-events-none",
  ].join(" "),
  {
    variants: {
      variant: {
        primary:
          "bg-action-primary text-action-primary-fg shadow-sm hover:bg-action-primary-hover active:brightness-[0.92] disabled:bg-action-disabled disabled:text-action-disabled-fg disabled:shadow-none",
        secondary:
          "border border-action-secondary-fg bg-transparent text-action-secondary-fg hover:bg-action-ghost-hover disabled:border-action-disabled disabled:text-action-disabled-fg disabled:hover:bg-transparent",
        ghost:
          "bg-transparent text-action-secondary-fg underline-offset-4 hover:underline disabled:opacity-50 disabled:hover:no-underline",
        destructive:
          "bg-status-danger-fill text-white shadow-sm hover:brightness-[0.92] disabled:bg-action-disabled disabled:text-action-disabled-fg",
      },
      size: {
        sm: "h-9 px-4 text-sm after:absolute after:-inset-1 after:content-['']",
        md: "h-11 px-6 text-sm",
        lg: "h-12 px-6 text-base",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
)

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    loading?: boolean
    icon?: React.ReactNode
  }

function Button({
  className,
  variant,
  size,
  loading = false,
  icon,
  disabled,
  type = "button",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      data-variant={variant}
      data-size={size}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {loading ? (
        <LoaderCircle className="animate-spin" aria-hidden="true" />
      ) : icon != null ? (
        icon
      ) : null}
      {children}
    </button>
  )
}

export { Button, buttonVariants }
