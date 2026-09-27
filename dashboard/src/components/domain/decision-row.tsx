/*
 * DecisionRow — one recorded human decision, audit-grade.
 *
 * Fixes the Decision-History defects: shows WHO (labeler), WHEN (ts),
 * WAS → NOW (old/new value) and the RATIONALE — accepted and stored
 * server-side but until now never sent by the UI nor displayed. When no
 * rationale exists the row says so honestly ("No rationale recorded"),
 * keeping the gap visible instead of hiding it.
 */

import type { Lang } from "@/lib/phrasebook";
import { t } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";
import { dt } from "./domain-strings";
import type { DecisionRecord } from "./domain-types";
import { DomChip } from "./ui-bits";

const FIELD_KEY: Record<string, Parameters<typeof dt>[1]> = {
  sif_label: "fieldVerdict",
  rules: "fieldRules",
  notes: "fieldNote",
};

function humanValue(field: string, value: string | null, lang: Lang): string {
  if (value == null || value === "") return "—";
  if (field === "sif_label") {
    if (value === "sif_potential") return dt(lang, "sifPotential");
    if (value === "not_sif_potential") return dt(lang, "notSifPotential");
  }
  return value;
}

export function DecisionRow({
  decision,
  lang = "en",
  className,
}: {
  decision: DecisionRecord;
  lang?: Lang;
  className?: string;
}) {
  const fieldLabel = FIELD_KEY[decision.field] ? dt(lang, FIELD_KEY[decision.field]) : decision.field;
  const when = new Intl.DateTimeFormat(lang === "hi" ? "hi-IN" : "en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(decision.ts));
  const rationale = decision.rationale?.trim() ?? "";
  return (
    <article
      className={cn(
        "flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-card px-3 py-2",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs leading-4 text-content-secondary">
        <span className="font-medium text-content-primary">{decision.labeler}</span>
        <span aria-hidden="true">·</span>
        <span>{when}</span>
        {decision.source === "blind_gold" ? <DomChip tone="info">{dt(lang, "blindGold")}</DomChip> : null}
      </div>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm leading-5 text-content-primary">
        <span className="text-xs text-content-secondary">{fieldLabel}</span>
        <span>
          <span className="text-xs text-content-secondary">{t(lang, "colWas")} </span>
          <span className="text-content-secondary">{humanValue(decision.field, decision.oldValue, lang)}</span>
          {" → "}
          <span className="text-xs text-content-secondary">{t(lang, "colNow")} </span>
          <span className="font-medium">{humanValue(decision.field, decision.newValue, lang)}</span>
        </span>
      </div>
      <p className="text-xs leading-4 break-words text-content-secondary">
        <span className="font-medium text-content-primary">{dt(lang, "decisionWhy")}: </span>
        {rationale || <em>{dt(lang, "decisionNoRationale")}</em>}
      </p>
    </article>
  );
}