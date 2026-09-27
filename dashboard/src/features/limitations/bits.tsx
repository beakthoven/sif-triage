import type { ReactNode } from "react";

export function Note({ children }: { children: ReactNode }) {
  return <p className="text-sm text-content-secondary">{children}</p>;
}
