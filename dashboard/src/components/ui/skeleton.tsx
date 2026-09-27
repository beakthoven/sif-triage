import { cn } from "@/lib/utils"

/**
 * Loading placeholder for a data surface that has no rows yet. aria-hidden —
 * announce loading state in the surface's own copy, not from the shimmer.
 */
function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("max-w-full animate-pulse rounded-md bg-surface-sunken", className)}
    />
  )
}

export { Skeleton }