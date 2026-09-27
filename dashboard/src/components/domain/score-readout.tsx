/*
 * ScoreReadout — numeric score + review-priority word + the SERVER's tuned
 * threshold + model version + stability. Never a bare number, and never a
 * client-side band: the threshold shown is the server operating point
 * (0.5647 for the masked-v2 artifact since the 2026-09-26 ensemble re-tune),
 * so a card can no longer read "flagged" at a score the metrics do not count.
 */

import { t, type Lang } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";
import { dt } from "./domain-strings";
import type { VerdictWord } from "./domain-types";
import { DomChip, type ChipTone } from "./ui-bits";
import { StabilityIndicator } from "./stability-indicator";
import { ScoreMeter } from "./score-meter";
import type { Stability } from "./domain-types";

const WORD_KEY: Record<VerdictWord, Parameters<typeof dt>[1]> = {
  HIGH: "wordHigh",
  MODERATE: "wordModerate",
  LOW: "wordLow",
  CLEAR: "wordClear",
  REVIEW: "wordReview",
};

const WORD_TONE: Record<VerdictWord, ChipTone> = {
  HIGH: "high",
  MODERATE: "moderate",
  LOW: "low",
  CLEAR: "clear",
  REVIEW: "uncertain",
};

export function ScoreReadout({
  score,
  band,
  threshold,
  stability,
  modelVersion,
  lang = "en",
  className,
}: {
  score: number;
  band: VerdictWord;
  /** The server's tuned operating point (flag_threshold). Required — a
   *  verdict may never render without naming the threshold it was decided
   *  against. */
  threshold: number;
  stability?: Stability | null;
  modelVersion?: string | null;
  lang?: Lang;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wider text-content-secondary uppercase">
            {t(lang, "triageScore")}
          </span>
          <span className="text-kpi-num text-content-primary">{score.toFixed(3)}</span>
        </div>
        <DomChip tone={WORD_TONE[band]} className="mb-1 text-sm">
          {dt(lang, WORD_KEY[band])}
        </DomChip>
      </div>
      <ScoreMeter score={score} band={band} threshold={threshold} />
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs text-content-secondary">
        <span>
          {dt(lang, "reviewThreshold")}{" "}
          <span className="font-mono text-content-primary">{threshold}</span>
          {" — "}
          {dt(lang, "serverOperatingPoint")}
        </span>
        {modelVersion ? (
          <span className="font-mono" title={modelVersion}>
            {dt(lang, "modelLabel")} {modelVersion}
          </span>
        ) : null}
      </div>
      {stability ? (
        <StabilityIndicator
          spread={stability.spread}
          nVariants={stability.nVariants}
          verdictFlips={stability.verdictFlips}
          lang={lang}
        />
      ) : null}
    </div>
  );
}