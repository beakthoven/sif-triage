import { Dialog } from "@/components/ui";
import { t as tShared, type Lang } from "@/lib/phrasebook";
import { LimitationsSection } from "./limitations-panel";
import { t } from "./strings";

/** The always-reachable limitations disclosure, opened from the shell footer. */
export function LimitationsDialog({
  lang,
  open,
  onOpenChange,
}: {
  lang: Lang;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      size="content"
      title={t(lang, "panelLimitations")}
      closeLabel={tShared(lang, "close")}
    >
      <LimitationsSection lang={lang} />
    </Dialog>
  );
}
