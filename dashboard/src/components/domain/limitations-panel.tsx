/*
 * LimitationsPanel — the honest-limitations disclosure, always reachable.
 * Ships the canonical bilingual list (from the redesign plan's honest-
 * limitations section) so the content lives in one place; callers may pass
 * `items` to extend or replace it. No metric numbers are hardcoded here —
 * settings surfaces pass exact figures via `items` when they want them.
 */

import type { Lang } from "@/lib/phrasebook";
import { cn } from "@/lib/utils";
import { dt } from "./domain-strings";
import type { LimitationItem } from "./domain-types";
import { DtLabel } from "./ui-bits";

export const DEFAULT_LIMITATIONS: Record<Lang, LimitationItem[]> = {
  en: [
    {
      title: "Training distribution is not OIL's register",
      body: "Labels derive from a US post-injury corpus plus synthetic text. Off-distribution text can score wrongly — an out-of-distribution stratum measured 0.00 recall. Novel text must be read, not trusted.",
    },
    {
      title: "Procedural barrier failures are under-detected by the score",
      body: "Absence of controls (no gas test, no LOTO, no fire watch) scores low. Deterministic barrier gates catch named absences — always read the barrier-failure list, never the score alone.",
    },
    {
      title: "Verdicts move under rephrasing",
      body: "The score varies when a report is rephrased. Self-consistency averaging narrows the spread (shown per report) but does not remove it; high spread routes to human review.",
    },
    {
      title: "Demo flag rate is a seeding artifact",
      body: "The demo database is seeded partly from training-corpus text, so it scores itself. Its flag rate is not a field measurement.",
    },
    {
      title: "No deployment-prevalence precision exists",
      body: "Precision figures were measured at a much higher prevalence than deployment would show; they do not transfer to a real queue.",
    },
    {
      title: "Hindi and mixed-language reports are routed, not translated",
      body: "Non-Latin text goes to human review without machine translation; no Devanagari rows exist in our data, so translation demand is unproven.",
    },
  ],
  hi: [
    {
      title: "प्रशिक्षण वितरण OIL की भाषा-शैली नहीं है",
      body: "लेबल एक अमेरिकी गंभीर-चोट संग्रह और कृत्रिम पाठ से बने हैं। अज्ञात शैली का पाठ गलत स्कोर कर सकता है — एक दायरे से बाहर की श्रेणी की स्मृति-दर 0.00 नापी गई।",
    },
    {
      title: "प्रक्रियात्मक अवरोध विफलताएँ स्कोर से कम पकड़ में आती हैं",
      body: "नियंत्रणों की अनुपस्थिति (गैस टेस्ट नहीं, LOTO नहीं, फायर वॉच नहीं) कम स्कोर करती है। नियतात्मक अवरोध जाँचें नामित अनुपस्थितियाँ पकड़ती हैं — केवल स्कोर नहीं, अवरोध सूची ज़रूर पढ़ें।",
    },
    {
      title: "शब्द बदलने पर निर्णय बदल सकता है",
      body: "रिपोर्ट के दूसरे शब्दों पर स्कोर बदलता है। स्व-संगति औसत फैलाव घटाता है (प्रति रिपोर्ट दिखाया गया) पर हटाता नहीं; अधिक फैलाव मानवीय समीक्षा को जाता है।",
    },
    {
      title: "डेमो चिह्नित दर सीडिंग का परिणाम है",
      body: "डेमो डेटाबेस आंशिक रूप से प्रशिक्षण-संग्रह पाठ से सीड किया गया है, इसलिए वह खुद को स्कोर करता है। उसकी चिह्नित दर क्षेत्र माप नहीं है।",
    },
    {
      title: "तैनाती-व्यापता पर परिशुद्धता मापी नहीं गई",
      body: "परिशुद्धता के आँकड़े तैनाती से कहीं अधिक व्यापता पर नापे गए थे; वे वास्तविक कतार पर लागू नहीं होते।",
    },
    {
      title: "हिंदी और मिश्रित-भाषा रिपोर्टें अनुवाद नहीं, रूट होती हैं",
      body: "गैर-लैटिन पाठ बिना मशीन-अनुवाद मानवीय समीक्षा को जाता है; हमारे डेटा में देवनागरी पंक्तियाँ नहीं हैं, अतः अनुवाद की माँग सिद्ध नहीं है।",
    },
  ],
};

export function LimitationsPanel({
  items,
  lang = "en",
  className,
}: {
  items?: LimitationItem[] | null;
  lang?: Lang;
  className?: string;
}) {
  const list = items && items.length > 0 ? items : DEFAULT_LIMITATIONS[lang];
  return (
    <section
      className={cn(
        "flex flex-col gap-2 rounded-lg border border-border-default bg-surface-card px-4 py-3",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <h3 className="text-lg leading-6 font-semibold text-content-primary">
          {dt(lang, "limitationsHeading")}
        </h3>
        <DtLabel>{dt(lang, "limitationsNote")}</DtLabel>
      </div>
      <ul className="flex list-disc flex-col gap-1.5 pl-5 marker:text-content-muted">
        {list.map((item, i) => (
          <li key={i} className="text-sm leading-5 text-content-primary">
            <span className="font-medium">{item.title}</span>
            {" — "}
            <span className="text-content-secondary">{item.body}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}