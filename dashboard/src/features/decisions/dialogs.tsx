/* DECISIONS dialogs — the amend (correct) flow and the CAPA closure flow.
 * Both honor the backend's append-only model: amend POSTs a new row (never a
 * mutation); CAPA is client-local state disclosed as such. */
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { Lang } from "@/lib/phrasebook";
import type { RuleInfo } from "@/lib/types";
import {
  amendDecision,
  suggestTrack,
  defaultDue,
  type AmendField,
  type AuditRow,
  type Capa,
  type OisdTrack,
  type ReportMeta,
} from "./data";
import { dt } from "./strings";
import { humanizeValue } from "./values";

export interface AmendDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lang: Lang;
  row: AuditRow | null;
  rules: RuleInfo[];
  reviewer: string;
  onReviewerChange: (name: string) => void;
  /** Called after a successful POST (parent refetches the log). */
  onSubmitted: () => void;
}

export function AmendDialog({
  open,
  onOpenChange,
  lang,
  row,
  rules,
  reviewer,
  onReviewerChange,
  onSubmitted,
}: AmendDialogProps) {
  const [field, setField] = useState<AmendField>("sif_label");
  const [value, setValue] = useState<string>("sif_potential");
  const [rationale, setRationale] = useState("");
  const [name, setName] = useState(reviewer);
  const [rationaleErr, setRationaleErr] = useState(false);
  const [valueErr, setValueErr] = useState(false);
  const [nameErr, setNameErr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!open || !row) return;
    const f = (row.field === "sif_label" || row.field === "rules" || row.field === "notes"
      ? row.field
      : "sif_label") as AmendField;
    setField(f);
    // Start from the corrected record's winning value when the vocabulary
    // matches; legacy band old_values are display-only.
    setValue(
      f === "sif_label"
        ? row.new_value === "not_sif_potential"
          ? "not_sif_potential"
          : "sif_potential"
        : f === "notes"
          ? ""
          : row.field === "rules"
            ? row.new_value.split(",")[0]?.trim() ?? (rules.find((r) => r.in_scope)?.key ?? "")
            : rules.find((r) => r.in_scope)?.key ?? "",
    );
    setRationale("");
    setName(reviewer);
    setRationaleErr(false);
    setValueErr(false);
    setNameErr(false);
    setFailed(false);
  }, [open, row, reviewer, rules]);

  if (!row) return null;

  const submit = async () => {
    const who = name.trim();
    const why = rationale.trim();
    const what = value.trim();
    const badName = who.length === 0;
    const badWhy = why.length === 0;
    const badWhat = what.length === 0 || (field === "rules" && !rules.some((r) => r.in_scope && r.key === what));
    setNameErr(badName);
    setRationaleErr(badWhy);
    setValueErr(badWhat);
    if (badName || badWhy || badWhat) return;
    setBusy(true);
    setFailed(false);
    try {
      await amendDecision({
        reportId: row.report_id,
        field,
        // old_value = the value this correction replaces: the prior decision's
        // winning value on the same field, else null (first record on it).
        oldValue: row.field === field ? row.new_value : null,
        newValue: what,
        labeler: who,
        rationale: why,
      });
      onReviewerChange(who);
      setBusy(false);
      onOpenChange(false);
      onSubmitted();
    } catch {
      setBusy(false);
      setFailed(true);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={dt(lang, "amendTitle")}
      description={dt(lang, "amendNotice")}
      closeLabel={dt(lang, "cancel")}
      footer={
        <>
          <Button variant="ghost" size="md" onClick={() => onOpenChange(false)}>
            {dt(lang, "cancel")}
          </Button>
          <Button variant="primary" size="md" loading={busy} onClick={() => void submit()}>
            {dt(lang, "amendSubmit")}
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <p className="text-sm text-content-secondary">
          <span className="font-mono">#{row.report_id}</span> · {humanizeValue(lang, row.new_value)}
        </p>
        <Field label={dt(lang, "reviewerHeading")} hint={dt(lang, "reviewerHint")} required error={nameErr ? dt(lang, "reviewerRequired") : undefined}>
          <Input
            value={name}
            invalid={nameErr}
            onChange={(e) => {
              setName(e.target.value);
              setNameErr(false);
            }}
            placeholder={dt(lang, "reviewerPlaceholder")}
          />
        </Field>
        <Field label={dt(lang, "amendField")}>
          <Select
            value={field}
            onChange={(v) => {
              const f = v as AmendField;
              setField(f);
              setValue(f === "sif_label" ? "sif_potential" : f === "rules" ? rules.find((r) => r.in_scope)?.key ?? "" : "");
            }}
            options={[
              { value: "sif_label", label: dt(lang, "fieldSifLabel") },
              { value: "rules", label: dt(lang, "fieldRules") },
              { value: "notes", label: dt(lang, "fieldNotes") },
            ]}
          />
        </Field>
        <Field label={dt(lang, "amendNewValue")} required error={valueErr ? dt(lang, "valueError") : undefined}>
          {field === "sif_label" ? (
            <Select
              value={value === "not_sif_potential" ? "not_sif_potential" : "sif_potential"}
              onChange={setValue}
              options={[
                { value: "sif_potential", label: dt(lang, "valSifPotential") },
                { value: "not_sif_potential", label: dt(lang, "valNotSifPotential") },
              ]}
            />
          ) : field === "rules" ? (
            <Select
              value={value}
              onChange={setValue}
              options={rules.filter((r) => r.in_scope).map((r) => ({
                value: r.key,
                label: r.display,
              }))}
            />
          ) : (
            <Textarea
              rows={3}
              invalid={valueErr}
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setValueErr(false);
              }}
            />
          )}
        </Field>
        <Field label={dt(lang, "rationaleLabel")} hint={dt(lang, "rationaleHint")} required error={rationaleErr ? dt(lang, "rationaleError") : undefined}>
          <Textarea
            rows={3}
            invalid={rationaleErr}
            value={rationale}
            onChange={(e) => {
              setRationale(e.target.value);
              setRationaleErr(false);
            }}
          />
        </Field>
        {failed && <p className="text-sm text-status-danger">{dt(lang, "amendFail")}</p>}
      </div>
    </Dialog>
  );
}

export interface CapaDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lang: Lang;
  row: AuditRow | null;
  meta: ReportMeta | null;
  existing: Capa | null;
  defaultOwner: string;
  onSave: (capa: Capa) => void;
}

export function CapaDialog({
  open,
  onOpenChange,
  lang,
  row,
  meta,
  existing,
  defaultOwner,
  onSave,
}: CapaDialogProps) {
  const [owner, setOwner] = useState("");
  const [due, setDue] = useState("");
  const [status, setStatus] = useState<"open" | "in_progress" | "closed">("open");
  const [track, setTrack] = useState<OisdTrack>("iir");
  const [ownerErr, setOwnerErr] = useState(false);

  useEffect(() => {
    if (!open || !row) return;
    setOwner(existing?.owner ?? defaultOwner);
    setTrack(existing?.track ?? suggestTrack(meta));
    setDue(existing?.due ?? defaultDue(existing?.track ?? suggestTrack(meta)));
    setStatus(existing?.status ?? "open");
    setOwnerErr(false);
  }, [open, row, existing, defaultOwner, meta]);

  if (!row) return null;

  const submit = () => {
    if (owner.trim().length === 0) {
      setOwnerErr(true);
      return;
    }
    onSave({ owner: owner.trim(), due, status, track });
    onOpenChange(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={dt(lang, "capaTitle")}
      description={dt(lang, "capaDesc")}
      closeLabel={dt(lang, "cancel")}
      footer={
        <>
          <Button variant="ghost" size="md" onClick={() => onOpenChange(false)}>
            {dt(lang, "cancel")}
          </Button>
          <Button variant="primary" size="md" onClick={submit}>
            {dt(lang, "capaSave")}
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <p className="text-sm text-content-secondary">
          <span className="font-mono">#{row.report_id}</span> · {humanizeValue(lang, row.new_value)}
        </p>
        <Field label={dt(lang, "ownerLabel")} required error={ownerErr ? dt(lang, "ownerRequired") : undefined}>
          <Input
            value={owner}
            invalid={ownerErr}
            onChange={(e) => {
              setOwner(e.target.value);
              setOwnerErr(false);
            }}
            placeholder={dt(lang, "reviewerPlaceholder")}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={dt(lang, "dueLabel")}>
            <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
          <Field label={dt(lang, "statusLabel")}>
            <Select
              value={status}
              onChange={(v) => setStatus(v as "open" | "in_progress" | "closed")}
              options={[
                { value: "open", label: dt(lang, "statusOpen") },
                { value: "in_progress", label: dt(lang, "statusInProgress") },
                { value: "closed", label: dt(lang, "statusClosed") },
              ]}
            />
          </Field>
        </div>
        <Field label={dt(lang, "trackLabel")}>
          <Select
            value={track}
            onChange={(v) => {
              const t = v as OisdTrack;
              setTrack(t);
              if (!existing) setDue(defaultDue(t));
            }}
            options={[
              { value: "fir", label: dt(lang, "trackFir") },
              { value: "iir", label: dt(lang, "trackIir") },
            ]}
          />
        </Field>
      </div>
    </Dialog>
  );
}
