import { LimitationsPanel } from "@/components/domain";
import type { LimitationItem } from "@/components/domain/domain-types";
import type { Lang } from "@/lib/phrasebook";
import { Note } from "./bits";
import { t } from "./strings";

/* LIMITATIONS — rendered THROUGH the domain LimitationsPanel (the contract's
 * always-reachable disclosure component); this slice supplies the canonical
 * 9-item list with evidence pointers. Each
 * item is verbatim-in-spirit from docs/redesign-plan.md §9 +
 * docs/discovery/60-orchestrator-novel-probe.md. The item contract is
 * {title, body}, so the evidence pointer is folded into the body. */
const LIM_KEYS = [
  { title: "lim1Title", body: "lim1Body", evidence: "lim1Evidence" },
  { title: "lim2Title", body: "lim2Body", evidence: "lim2Evidence" },
  { title: "lim3Title", body: "lim3Body", evidence: "lim3Evidence" },
  { title: "lim4Title", body: "lim4Body", evidence: "lim4Evidence" },
  { title: "lim5Title", body: "lim5Body", evidence: "lim5Evidence" },
  { title: "lim6Title", body: "lim6Body", evidence: "lim6Evidence" },
  { title: "lim7Title", body: "lim7Body", evidence: "lim7Evidence" },
  { title: "lim8Title", body: "lim8Body", evidence: "lim8Evidence" },
  { title: "lim9Title", body: "lim9Body", evidence: "lim9Evidence" },
] as const;

/** Evidence-backed items for the domain panel. */
export function limitationItems(lang: Lang): LimitationItem[] {
  return LIM_KEYS.map((k) => ({
    title: t(lang, k.title),
    body: `${t(lang, k.body)} (${t(lang, "evidenceLabel")}: ${t(lang, k.evidence)})`,
  }));
}

export function LimitationsSection({ lang }: { lang: Lang }) {
  return (
    <section
      id="limitations"
      aria-label={t(lang, "panelLimitations")}
      className="scroll-mt-24 space-y-2"
    >
      <Note>{t(lang, "limitationsIntro")}</Note>
      <LimitationsPanel items={limitationItems(lang)} lang={lang} />
    </section>
  );
}
