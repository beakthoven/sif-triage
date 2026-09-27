/* DECISIONS value humanization — one vocabulary per display concept.
 * Legacy rows wrote the client-derived band ("HIGH") as old_value; those are
 * shown with a "band (legacy)" marker so the audit table never presents two
 * vocabularies as the same thing (discovery 13 finding 5). */
import { dt } from "./strings";
import type { Lang } from "@/lib/phrasebook";

export function humanizeField(lang: Lang, field: string): string {
  if (field === "sif_label") return dt(lang, "fieldSifLabel");
  if (field === "rules") return dt(lang, "fieldRules");
  if (field === "notes") return dt(lang, "fieldNotes");
  return field.replaceAll("_", " ");
}

export function humanizeValue(lang: Lang, value: string | null): string {
  if (!value) return dt(lang, "rationaleNone");
  switch (value) {
    case "sif_potential":
      return dt(lang, "valSifPotential");
    case "not_sif_potential":
      return dt(lang, "valNotSifPotential");
    case "HIGH":
    case "MODERATE":
    case "LOW": {
      const word =
        value === "HIGH"
          ? dt(lang, "bandHigh")
          : value === "MODERATE"
            ? dt(lang, "bandModerate")
            : dt(lang, "bandLow");
      return `${word} · ${dt(lang, "bandNote")}`;
    }
    default:
      return value;
  }
}

/** Chip tone for a report's severity band — words always ride along (the Chip
 *  primitive renders the word; tone carries the token). */
export function bandTone(band: string | null): "high" | "moderate" | "low" {
  return band === "HIGH" ? "high" : band === "MODERATE" ? "moderate" : "low";
}

export function bandWord(lang: Lang, band: string | null): string {
  return band === "HIGH"
    ? dt(lang, "bandHigh")
    : band === "MODERATE"
      ? dt(lang, "bandModerate")
      : band === "LOW"
        ? dt(lang, "bandLow")
        : dt(lang, "bandUnknown");
}

export function bandRank(band: string | null): number {
  return band === "HIGH" ? 3 : band === "MODERATE" ? 2 : band === "LOW" ? 1 : 0;
}
