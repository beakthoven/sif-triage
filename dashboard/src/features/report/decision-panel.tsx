import { useEffect, useRef, useState } from "react";
import { CircleCheck, CircleMinus, OctagonAlert } from "lucide-react";
import { Button, Field, Input, Textarea } from "@/components/ui";
import { type Lang } from "@/lib/phrasebook";
import { DEFAULT_REVIEWER, REVIEWER_KEY } from "@/lib/identity";
import type { OverrideOut, Report } from "@/lib/types";
import { c } from "./copy";

/* A recorded sif_label decision (latest-wins) for one report: WHICH decision,
 * its RATIONALE, who recorded it and when. OverrideOut in @/lib/types carries
 * rationale on the wire contract; older rows may still have null. */
export interface RecordedDecision {
  decision: "confirm" | "reject";
  rationale: string;
  labeler: string;
  ts: string;
}

export function latestLabelDecision(overrides: OverrideOut[]): RecordedDecision | null {
  const rows = [...overrides]
    .filter((o) => o.field === "sif_label")
    .sort((a, b) => b.ts.localeCompare(a.ts) || b.id - a.id);
  const last = rows[0];
  if (!last) return null;
  return {
    decision: last.new_value === "not_sif_potential" ? "reject" : "confirm",
    rationale: last.rationale ?? "",
    labeler: last.labeler,
    ts: last.ts,
  };
}

/**
 * The decision record for one report. The confirm / not-SIF entry point is
 * the unified verdict card's footer (one decision control per screen, spec §4
 * — this panel's own buttons were deliberately removed); its callbacks land
 * here as `pending`, and the amend path reopens the same form. The form
 * requires a RATIONALE and records reviewer identity. A rejected write shows
 * an honest error and keeps the form values — a fake success on a safety
 * screen is the one thing this panel must never do.
 */
export function DecisionPanel({
  report,
  lang,
  recorded,
  submitting,
  submitError,
  overridesError,
  onSubmit,
  onDismissError,
  pending = null,
  onPendingHandled,
}: {
  report: Report;
  lang: Lang;
  recorded: RecordedDecision | null;
  submitting: boolean;
  submitError: string | null;
  overridesError: string | null;
  onSubmit: (
    choice: "confirm" | "reject",
    rationale: string,
    reviewer: string,
  ) => Promise<boolean>;
  onDismissError: () => void;
  /** Entry point shared with the unified card's onConfirm/onReject. */
  pending?: "confirm" | "reject" | null;
  onPendingHandled?: () => void;
}) {
  const [choice, setChoice] = useState<"confirm" | "reject" | null>(null);
  const [rationale, setRationale] = useState("");
  const [reviewer, setReviewer] = useState(() => {
    try {
      return (
        localStorage.getItem(REVIEWER_KEY) ||
        localStorage.getItem("sif.reviewer") ||
        DEFAULT_REVIEWER
      );
    } catch {
      return DEFAULT_REVIEWER;
    }
  });
  const [amending, setAmending] = useState(false);

  const sectionRef = useRef<HTMLElement | null>(null);

  // The unified card's onConfirm/onReject land here as `pending`.
  useEffect(() => {
    if (pending) {
      setAmending(false);
      setChoice(pending);
      onPendingHandled?.();
      sectionRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [pending, onPendingHandled]);

  // A newly recorded decision (or a different report) closes the form.
  useEffect(() => {
    setChoice(null);
    setRationale("");
    setAmending(false);
  }, [recorded, report.id]);

  const formOpen = choice !== null || amending;
  const canSubmit =
    choice !== null && rationale.trim().length > 0 && reviewer.trim().length > 0 && !submitting;

  async function submit() {
    if (choice === null) return;
    try {
      localStorage.setItem(REVIEWER_KEY, reviewer.trim());
    } catch {
      // Keep the decision flow available when browser storage is disabled.
    }
    const ok = await onSubmit(choice, rationale.trim(), reviewer.trim());
    if (ok) setRationale("");
  }

  return (
    <section
      ref={sectionRef}
      aria-label={c(lang, "decisionHeading")}
      className="scroll-mt-24 space-y-4 rounded-md border border-border-subtle bg-surface-card p-6 shadow-sm md:p-8"
    >
      <div className="flex items-start gap-3">
        <h2 className="text-lg font-semibold text-content-primary">{c(lang, "decisionHeading")}</h2>
      </div>

      {overridesError && (
        <p role="note" className="text-sm text-content-secondary">
          {c(lang, "overridesError")}
          <span className="ml-2 font-mono text-xs text-content-muted">{overridesError}</span>
        </p>
      )}

      {submitError && (
        <div
          role="alert"
          className="flex gap-3 rounded-md border-l-4 border-status-danger-fill bg-verdict-high-chip px-4 py-3"
        >
          <OctagonAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-status-danger" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-status-danger">{c(lang, "decisionFailed")}</p>
            <p className="mt-1 font-mono text-xs text-content-secondary">{submitError}</p>
            <Button variant="ghost" size="sm" className="mt-2 -ml-4" onClick={onDismissError}>
              {c(lang, "cancel")}
            </Button>
          </div>
        </div>
      )}

      {recorded && !formOpen ? (
        <div role="status" className="rounded-md border border-border-subtle bg-surface-zebra p-4">
          <p className="text-xs font-semibold tracking-wider text-content-secondary uppercase">
            {c(lang, "recordedLabel")}
          </p>
          <p className="mt-2 inline-flex items-center gap-2 text-base font-semibold">
            {recorded.decision === "confirm" ? (
              <CircleCheck aria-hidden="true" className="size-5 text-status-ok" />
            ) : (
              <CircleMinus aria-hidden="true" className="size-5 text-content-secondary" />
            )}
            <span className={recorded.decision === "confirm" ? "text-status-ok" : "text-content-primary"}>
              {recorded.decision === "confirm" ? c(lang, "recordedConfirm") : c(lang, "recordedNotSif")}
            </span>
          </p>
          {recorded.rationale ? (
            <blockquote className="mt-3 border-l-2 border-border-strong pl-4 text-base text-content-primary">
              {recorded.rationale}
            </blockquote>
          ) : (
            <p className="mt-2 text-sm text-content-secondary">{c(lang, "recordedNoRationale")}</p>
          )}
          <p className="mt-3 font-mono text-xs text-content-secondary">
            {c(lang, "recordedBy")} {recorded.labeler} · {recorded.ts.replace("T", " ").slice(0, 16)}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setAmending(true);
                setChoice(recorded.decision);
                setRationale(recorded.rationale);
              }}
            >
              {c(lang, "amend")}
            </Button>
            <p className="max-w-prose text-xs text-content-secondary">{c(lang, "amendNote")}</p>
          </div>
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
          className="space-y-4 rounded-md border border-border-default bg-surface-zebra p-4 md:p-6"
        >
          <div className="flex flex-wrap gap-3" role="group" aria-label={c(lang, "decisionHeading")}>
            <Button
              variant={choice === "confirm" ? "primary" : "secondary"}
              aria-pressed={choice === "confirm"}
              onClick={() => setChoice("confirm")}
            >
              {c(lang, "chooseConfirm")}
            </Button>
            <Button
              variant={choice === "reject" ? "primary" : "secondary"}
              aria-pressed={choice === "reject"}
              onClick={() => setChoice("reject")}
            >
              {c(lang, "chooseNotSif")}
            </Button>
          </div>
          {choice !== null && (
            <p className="text-base font-semibold text-content-primary">
              {choice === "confirm" ? c(lang, "recordedConfirm") : c(lang, "recordedNotSif")}
            </p>
          )}
          <Field label={c(lang, "rationaleLabel")} required>
            <Textarea
              rows={3}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder={c(lang, "rationalePlaceholder")}
            />
          </Field>
          <Field label={c(lang, "reviewerLabel")} hint={c(lang, "reviewerHint")}>
            <Input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              className="font-mono"
            />
          </Field>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" size="md" type="submit" disabled={!canSubmit}>
              {c(lang, "recordDecision")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              type="button"
              onClick={() => {
                setChoice(null);
                setAmending(false);
                onDismissError();
              }}
            >
              {c(lang, "cancel")}
            </Button>
            {rationale.trim().length === 0 && (
              <p className="text-sm text-content-secondary">{c(lang, "rationaleRequired")}</p>
            )}
          </div>
        </form>
      )}
    </section>
  );
}
