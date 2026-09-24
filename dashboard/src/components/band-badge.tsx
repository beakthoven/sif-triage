import type { Band } from "@/lib/types";
import { t, type Lang } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";

const BAND_STYLE: Record<Band, { dot: string; text: string }> = {
  HIGH: { dot: "bg-verdict", text: "text-verdict" },
  MODERATE: { dot: "bg-verdict", text: "text-verdict" },
  LOW: { dot: "bg-ok", text: "text-ok" },
};

/** Review-priority band — small text label with a 6px dot, never a pill.
 *  Words carry the meaning; the dot only reinforces (never color-only). */
export function BandBadge({
  band,
  lang,
  className,
}: {
  band: Band;
  lang: Lang;
  className?: string;
}) {
  const s = BAND_STYLE[band];
  const label = t(
    lang,
    band === "HIGH" ? "highPriority" : band === "MODERATE" ? "moderatePriority" : "noAction",
  );
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap",
        s.text,
        className,
      )}
    >
      <span className={cn("status-dot", s.dot)} aria-hidden />
      {label}
    </span>
  );
}
