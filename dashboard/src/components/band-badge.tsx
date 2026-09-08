import type { Band } from "@/lib/types";
import { cn } from "@/lib/utils";

const BAND_STYLES: Record<Band, string> = {
  HIGH: "bg-primary text-primary-foreground",
  MODERATE: "bg-accent text-accent-foreground",
  LOW: "bg-muted text-muted-foreground",
};

/** Review-priority band chip — icon + text, never color-only. */
export function BandBadge({ band, className }: { band: Band; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 font-mono text-sm font-semibold tracking-wide",
        BAND_STYLES[band],
        className,
      )}
    >
      <span aria-hidden>{band === "HIGH" ? "▲" : band === "MODERATE" ? "◆" : "▽"}</span>
      {band} REVIEW PRIORITY
    </span>
  );
}
