import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { t, type Lang } from "@/lib/phrasebook";

/**
 * The demo's opening beat: paste a raw UA/UC / near-miss report, Classify,
 * and the scored triage card (or gray Sentinel card) lands in the feed panel.
 * Ctrl+Enter submits. Presentational — FeedView owns the classify call,
 * the busy skeleton, and the offline placeholder note.
 */
export function PasteClassify({
  lang,
  text,
  busy,
  offline,
  onTextChange,
  onSubmit,
}: {
  lang: Lang;
  text: string;
  busy: boolean;
  offline: boolean;
  onTextChange: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <Card className="border-border py-0">
      <CardContent className="space-y-3 px-5 py-4">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {t(lang, "pasteTitle")}
        </p>
        <textarea
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
              e.preventDefault();
              onSubmit();
            }
          }}
          rows={3}
          placeholder={t(lang, "pastePlaceholder")}
          aria-label={t(lang, "pasteTitle")}
          className="min-h-20 w-full rounded-md border border-input bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="lg"
            onClick={onSubmit}
            disabled={busy || !text.trim()}
            className="min-h-11"
          >
            {busy && <Loader2 className="animate-spin" aria-hidden />}
            {busy ? t(lang, "pasteBusy") : t(lang, "pasteButton")}
          </Button>
          <span className="font-mono text-xs text-muted-foreground">
            {t(lang, "pasteHint")}
          </span>
          {offline && (
            <span className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
              <span className="status-dot bg-quiet" aria-hidden />
              {t(lang, "offlineNote")}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
