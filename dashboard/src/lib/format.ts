import type { Lang } from "@/lib/phrasebook";

const EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;

function parseIsoDate(iso: string | null | undefined): { y: number; m: number; d: number } | null {
  if (!iso) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (!match) return null;
  const y = Number(match[1]);
  const m = Number(match[2]);
  const d = Number(match[3]);
  if (m < 1 || m > 12 || d < 1 || d > 31) return null;
  return { y, m, d };
}

/** DESIGN §6.6: "26 Sep 2026", never an ambiguous numeric date.
 *  Date-only ISO strings are read as calendar dates, not UTC instants. */
export function formatDisplayDate(iso: string | null | undefined, lang: Lang = "en"): string {
  const parts = parseIsoDate(iso);
  if (!parts) return iso?.trim() ? iso.trim() : "—";
  if (lang === "hi") {
    return new Date(parts.y, parts.m - 1, parts.d).toLocaleDateString("hi-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }
  return `${parts.d} ${EN_MONTHS[parts.m - 1]} ${parts.y}`;
}

export function formatLocalDate(date: Date, lang: Lang = "en"): string {
  const iso = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  return formatDisplayDate(iso, lang);
}
