import type { Report } from "@/lib/types";

const MISSING_VALUES = new Set([
  "",
  "(unspecified)",
  "(live paste)",
  "Site not provided",
  "Activity not provided",
  "साइट उपलब्ध नहीं",
  "गतिविधि उपलब्ध नहीं",
]);

const LOCATION_CUE =
  /\b(site|area|field|plant|station|terminal|yard|road|rig|well|ggs|gcs|ctf|eps|workshop|warehouse|stores|facility|installation|platform)\b/i;

export function hasFacet(value: string | null | undefined): value is string {
  return Boolean(value && !MISSING_VALUES.has(value.trim()));
}

/** Infer only explicit leading location headers, never arbitrary narrative. */
export function inferredSite(text: string): string | null {
  const labelled = text.match(
    /^\s*(?:site|location|field|installation|plant)\s*[:\-–—]\s*([^.\n]{2,80})/i,
  );
  if (labelled?.[1]) return labelled[1].trim().replace(/[\s:;,–—-]+$/, "");

  for (const match of text.matchAll(/\b(?:at|near|inside|within)\s+(?:the\s+)?([^,.;\n]{2,60})/gi)) {
    const candidate = match[1]?.trim().replace(/[\s:;,–—-]+$/, "");
    if (candidate && LOCATION_CUE.test(candidate)) return candidate;
  }

  const firstClause = text.split(/[.\n]/, 1)[0]?.trim();
  if (
    firstClause &&
    firstClause.length <= 80 &&
    LOCATION_CUE.test(firstClause)
  ) {
    return firstClause.replace(/[\s:;,–—-]+$/, "");
  }
  return null;
}

function reportTitle(text: string): string | null {
  const sentence = text.split(/[.!?\n]/, 1)[0]?.replace(/\s+/g, " ").trim();
  if (!sentence) return null;
  return sentence.length <= 72 ? sentence : `${sentence.slice(0, 69).trimEnd()}…`;
}

export function reportSiteLabel(report: Report): string {
  return hasFacet(report.site)
    ? report.site
    : inferredSite(report.text) ?? reportTitle(report.text) ?? `Report #${report.id}`;
}

export function reportActivityLabel(report: Report): string | null {
  return hasFacet(report.activity) ? report.activity : null;
}
