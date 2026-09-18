"use client";

import { useSyncExternalStore } from "react";

/**
 * SSR-safe media query hook (server snapshot defaults to `false`, so the
 * desktop layout renders first and the client corrects on hydration if
 * needed -- avoids a hydration mismatch warning).
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onStoreChange) => {
      const mediaQueryList = window.matchMedia(query);
      mediaQueryList.addEventListener("change", onStoreChange);
      return () => mediaQueryList.removeEventListener("change", onStoreChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
