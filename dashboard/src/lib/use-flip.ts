import { useLayoutEffect, useRef } from "react";

/**
 * Minimal FLIP hook for the density re-rank animation.
 * Remembers each keyed row's vertical position at the previous commit;
 * after a re-sort commit, inverts the delta and transitions to zero (600ms).
 * Static swap under prefers-reduced-motion.
 */
export function useFlip(depKey: unknown) {
  const els = useRef(new Map<string, HTMLElement>());
  const tops = useRef(new Map<string, number>());

  const setRef = (key: string) => (el: HTMLElement | null) => {
    if (el) els.current.set(key, el);
    else els.current.delete(key);
  };

  useLayoutEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    els.current.forEach((el, key) => {
      const now = el.getBoundingClientRect().top;
      const prev = tops.current.get(key);
      if (prev !== undefined && prev !== now && !reduced) {
        el.style.transition = "none";
        el.style.transform = `translateY(${prev - now}px)`;
        requestAnimationFrame(() => {
          el.style.transition = "transform 600ms cubic-bezier(0.22, 1, 0.36, 1)";
          el.style.transform = "";
        });
      }
      tops.current.set(key, now);
    });
  }, [depKey]);

  return setRef;
}
