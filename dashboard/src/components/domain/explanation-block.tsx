/*
 * ExplanationBlock — "Why this score?" reasoning: the deterministic template
 * always; the optional Ollama rewording when the source is the LLM (with the
 * template preserved behind a disclosure). Cached/LLM provenance is labelled,
 * and any leaked vector math is stripped from reviewer-facing copy.
 */

import type { Lang } from "@/lib/phrasebook";
import { t } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";
import { stripVectorMath } from "./domain-logic";
import { dt } from "./domain-strings";
import type { ExplanationView } from "./domain-types";
import { DomChip, DtLabel } from "./ui-bits";

export function ExplanationBlock({
  template,
  source = "template",
  cached = false,
  reworded,
  lang = "en",
  className,
}: ExplanationView & {
  lang?: Lang;
  className?: string;
}) {
  const templateText = template?.trim() ?? "";
  const rewordedText = reworded?.trim() ?? "";
  if (!templateText && !rewordedText) {
    return (
      <p className={cn("text-xs leading-4 text-content-secondary", className)}>
        {t(lang, "explanationUnavailable")}
      </p>
    );
  }
  const useReworded = source === "ollama" && rewordedText.length > 0;
  return (
    <section className={cn("flex flex-col gap-2", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <DtLabel>{t(lang, "whyScore")}</DtLabel>
        {cached ? <DomChip tone="neutral">{t(lang, "cached")}</DomChip> : null}
        {useReworded ? <DomChip tone="info">{t(lang, "llmPhrased")}</DomChip> : null}
      </div>
      <p className="text-base break-words text-content-primary">
        {stripVectorMath(useReworded ? rewordedText : templateText)}
      </p>
      {useReworded && templateText && templateText !== rewordedText ? (
        <details className="group rounded-md border border-border-subtle bg-surface-sunken px-3 py-2">
          <summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium text-content-link marker:content-none">
            {dt(lang, "explanationTemplateLine")}
          </summary>
          <p className="text-xs leading-4 break-words text-content-secondary">
            {stripVectorMath(templateText)}
          </p>
        </details>
      ) : null}
    </section>
  );
}