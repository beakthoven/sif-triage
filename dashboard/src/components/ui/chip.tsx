import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { CircleCheck, CircleHelp, CircleMinus, CircleX, Info, OctagonAlert, TriangleAlert } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Status pill (DESIGN §5.4): radius-full, chip tint + text-safe shade, and a
 * 16px icon left of the word. Tone is never the only signal — the caller
 * ALWAYS renders the word (HIGH / MODERATE / CLEAR / …) as children, and the
 * tone contributes its icon.
 */
const chipVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1 rounded-full font-semibold whitespace-nowrap transition-colors duration-220 ease-standard",
  {
    variants: {
      tone: {
        high: "bg-verdict-high-chip text-verdict-high",
        moderate: "bg-verdict-moderate-chip text-verdict-moderate",
        low: "bg-verdict-low-chip text-verdict-low",
        clear: "bg-verdict-clear-chip text-verdict-clear",
        uncertain: "bg-verdict-uncertain-chip text-verdict-uncertain",
        neutral: "bg-surface-sunken text-content-secondary",
        danger: "bg-verdict-high-chip text-status-danger",
        info: "bg-verdict-uncertain-chip text-status-info",
      },
      size: {
        sm: "py-0.5 pr-2 pl-1.5 text-xs [&_svg]:size-3.5",
        md: "py-1 pr-2 pl-1.5 text-xs [&_svg]:size-4",
      },
    },
    defaultVariants: {
      tone: "neutral",
      size: "md",
    },
  },
)

type Tone = NonNullable<VariantProps<typeof chipVariants>["tone"]>

const TONE_ICON: Record<Tone, React.ComponentType<{ className?: string; "aria-hidden"?: boolean }> | null> = {
  high: OctagonAlert,
  moderate: TriangleAlert,
  low: CircleMinus,
  clear: CircleCheck,
  uncertain: CircleHelp,
  neutral: null,
  danger: CircleX,
  info: Info,
}

type ChipProps = React.ComponentProps<"span"> &
  VariantProps<typeof chipVariants> & {
    /** Override the tone icon; `false` hides it (only for neutral meta tags). */
    icon?: React.ReactNode | false
  }

function Chip({ className, tone, size, icon, children, ...props }: ChipProps) {
  const ToneIcon = TONE_ICON[tone ?? "neutral"]
  const glyph =
    icon === false ? null : icon != null ? icon : ToneIcon ? <ToneIcon aria-hidden={true} /> : null
  return (
    <span
      data-tone={tone}
      data-size={size}
      className={cn(chipVariants({ tone, size }), glyph == null && "pl-2", className)}
      {...props}
    >
      {glyph}
      {children}
    </span>
  )
}

export { Chip, chipVariants, TONE_ICON }
