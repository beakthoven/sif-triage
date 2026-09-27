/*
 * Tiny shared presentational bits for the domain slice, delegating to the
 * @/components/ui primitives so verdict chips carry the same icon + word
 * pattern everywhere (DESIGN §5.4).
 */

import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { cn } from "@/lib/utils";

export type ChipTone =
  | "high"
  | "moderate"
  | "low"
  | "clear"
  | "uncertain"
  | "neutral"
  | "danger"
  | "info";

/** Always renders its word — tone never stands alone. */
export function DomChip({
  tone = "neutral",
  children,
  title,
  className,
}: {
  tone?: ChipTone;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <Chip tone={tone} title={title} className={className}>
      {children}
    </Chip>
  );
}

export function DomButton({
  variant = "secondary",
  size = "md",
  onClick,
  disabled,
  children,
  className,
}: {
  variant?: "primary" | "secondary" | "ghost" | "destructive";
  size?: "sm" | "md";
  onClick?: () => void;
  disabled?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Button variant={variant} size={size} onClick={onClick} disabled={disabled} className={className}>
      {children}
    </Button>
  );
}

/** Small uppercase section label. */
export function DtLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "text-xs font-semibold tracking-wider text-content-secondary uppercase",
        className,
      )}
    >
      {children}
    </span>
  );
}
