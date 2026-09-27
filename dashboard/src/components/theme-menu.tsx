import { DropdownMenu } from "radix-ui";
import { Check, Monitor, Moon, Sun } from "lucide-react";
import { t, type Lang } from "@/lib/phrasebook";
import { useTheme, type ThemePreference } from "@/lib/theme";
import { cn } from "@/lib/utils";

const OPTIONS: { value: ThemePreference; icon: typeof Sun; key: "themeLight" | "themeDark" | "themeSystem" }[] = [
  { value: "light", icon: Sun, key: "themeLight" },
  { value: "dark", icon: Moon, key: "themeDark" },
  { value: "system", icon: Monitor, key: "themeSystem" },
];

/** Header theme picker — trigger shows the resolved theme; the menu offers
 *  light / dark / follow-system. */
export function ThemeMenu({ lang }: { lang: Lang }) {
  const { preference, resolved, setPreference } = useTheme();
  const TriggerIcon = resolved === "dark" ? Moon : Sun;
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        aria-label={`${t(lang, "themeLabel")}: ${t(lang, OPTIONS.find((o) => o.value === preference)!.key)}`}
        className="grid size-11 place-items-center rounded-md text-chrome-fg-muted transition-colors duration-150 hover:bg-chrome-bg-hover hover:text-chrome-fg data-[state=open]:bg-chrome-bg-hover data-[state=open]:text-chrome-fg"
      >
        <TriggerIcon aria-hidden="true" className="size-5" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 min-w-44 rounded-md border border-border-subtle bg-surface-raised p-1 shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-top-1 data-[state=open]:duration-220 data-[state=open]:ease-decelerate data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:duration-150 data-[state=closed]:ease-accelerate"
        >
          <DropdownMenu.Label className="px-3 pt-2 pb-1 text-xs font-semibold text-content-secondary">
            {t(lang, "themeLabel")}
          </DropdownMenu.Label>
          <DropdownMenu.RadioGroup value={preference} onValueChange={(v) => setPreference(v as ThemePreference)}>
            {OPTIONS.map(({ value, icon: Icon, key }) => (
              <DropdownMenu.RadioItem
                key={value}
                value={value}
                className={cn(
                  "flex min-h-11 cursor-pointer items-center gap-3 rounded-sm px-3 text-sm text-content-primary outline-none transition-colors duration-150",
                  "data-[highlighted]:bg-action-ghost-hover data-[state=checked]:font-semibold",
                )}
              >
                <Icon aria-hidden="true" className="size-4 text-content-secondary" />
                <span className="flex-1">{t(lang, key)}</span>
                <DropdownMenu.ItemIndicator>
                  <Check aria-hidden="true" className="size-4 text-content-link" />
                </DropdownMenu.ItemIndicator>
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/** Inline, labelled variant for the mobile navigation panel. */
export function ThemeSegmented({ lang }: { lang: Lang }) {
  const { preference, setPreference } = useTheme();
  return (
    <div role="radiogroup" aria-label={t(lang, "themeLabel")} className="grid grid-cols-3 gap-1 rounded-md border border-border-subtle bg-surface-sunken p-1">
      {OPTIONS.map(({ value, icon: Icon, key }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={preference === value}
          onClick={() => setPreference(value)}
          className={cn(
            "flex min-h-11 items-center justify-center gap-2 rounded-sm text-sm font-semibold transition-colors duration-150",
            preference === value
              ? "bg-surface-card text-content-primary shadow-sm"
              : "text-content-secondary hover:text-content-primary",
          )}
        >
          <Icon aria-hidden="true" className="size-4" />
          {t(lang, key)}
        </button>
      ))}
    </div>
  );
}
