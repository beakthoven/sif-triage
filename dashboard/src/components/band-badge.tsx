import type { Band } from "@/lib/types";
import { cn } from "@/lib/utils";

const BAND_STYLE: Record<Band, { dot: string; text: string; label: string }> = {
  HIGH: { dot: "bg-verdict", text: "text-verdict", label: "High review priority" },
  MODERATE: { dot: "bg-verdict", text: "text-verdict", label: "Moderate review priority" },
  LOW: { dot: "bg-ok", text: "text-ok", label: "Low review priority" },
};

/** Review-priority band — small text label with a 6px dot, never a pill.
 *  Words carry the meaning; the dot only reinforces (never color-only). */
export function BandBadge({ band, className }: { band: Band; className?: string }) {
  const s = BAND_STYLE[band];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap",
        s.text,
        className,
      )}
    >
      <span className={cn("status-dot", s.dot)} aria-hidden />
      {s.label}
    </span>
  );
}
