/*
 * BarrierList — renders the barrier-failure gate family (workstream A2:
 * no gas test, no LOTO, no permit, no fire watch, no standby, unmonitored
 * atmosphere) that fired on this report. These name the ABSENT safeguard the
 * score may have missed — the D3 gap — and always route to human review.
 * Critical banner pattern (DESIGN §5.8): chip tint, text-safe shade, icon;
 * never dismissible.
 */

import { OctagonAlert } from "lucide-react";
import type { Lang } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";
import { dt } from "./domain-strings";
import type { BarrierState } from "./domain-types";
import { DomChip } from "./ui-bits";

function barrierSummary(lang: Lang, gate: string, label: string): string {
  const summary: Record<string, Record<Lang, string>> = {
    energy_isolation_absent: { en: "Isolation was not confirmed.", hi: "पृथक्करण की पुष्टि नहीं हुई।" },
    gas_test_absent: { en: "No gas test was recorded before entry.", hi: "प्रवेश से पहले गैस परीक्षण दर्ज नहीं हुआ।" },
    permit_absent: { en: "No permit was recorded for this work.", hi: "इस काम का परमिट दर्ज नहीं हुआ।" },
    fire_watch_absent: { en: "No fire watch was recorded.", hi: "फायर वॉच दर्ज नहीं था।" },
    standby_absent: { en: "No standby person was recorded.", hi: "स्टैंडबाय व्यक्ति दर्ज नहीं था।" },
    atmosphere_unmonitored: { en: "Atmosphere monitoring was not recorded.", hi: "वायुमंडल निगरानी दर्ज नहीं थी।" },
  };
  return summary[gate]?.[lang] ?? label;
}

export function BarrierList({
  barriers,
  lang = "en",
  className,
}: {
  barriers?: BarrierState[] | null;
  lang?: Lang;
  className?: string;
}) {
  if (!barriers || barriers.length === 0) return null;
  return (
    <section
      aria-label={dt(lang, "barrierHeading")}
      className={cn(
        "flex gap-3 rounded-md border-l-4 border-verdict-high-fill bg-verdict-high-chip px-4 py-4",
        className,
      )}
    >
      <OctagonAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-verdict-high" />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-base font-semibold text-content-primary">{dt(lang, "barrierHeading")}</span>
          <DomChip tone="high">{dt(lang, "barrierAbsentChip")}</DomChip>
        </div>
        <ul className="flex flex-col gap-2">
          {barriers.map((barrier, i) => (
            <li key={`${barrier.gate}-${i}`} className="flex flex-col gap-0.5">
              <span className="text-sm font-semibold text-content-primary">{barrier.label}</span>
              <p className="text-sm text-content-secondary">{barrierSummary(lang, barrier.gate, barrier.label)}</p>
            </li>
          ))}
        </ul>
        <p className="text-xs text-content-secondary">{dt(lang, "barrierNote")}</p>
      </div>
    </section>
  );
}
