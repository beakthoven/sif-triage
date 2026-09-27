import * as React from "react"
import { MotionConfig } from "motion/react"

/**
 * Every animated component in the app renders inside this provider.
 *
 * `motion` (and the motion-primitives interaction layer built on it) ships no
 * prefers-reduced-motion handling of its own; `reducedMotion="user"` disables
 * transform/layout animations for users whose OS asks for less motion.
 * Motion in this product clarifies state change (a report moving into REVIEW,
 * ingest progress) — it never decorates.
 */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>
}
