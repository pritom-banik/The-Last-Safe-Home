import { useSyncExternalStore } from "react";

/** Desktop layout from 1024 px (SPEC §10.2); below that the mobile layout with bottom sheets. */
export const DESKTOP_QUERY = "(min-width: 1024px)";

export function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(query);
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => window.matchMedia(query).matches,
    () => true,
  );
}

export const useIsDesktop = () => useMedia(DESKTOP_QUERY);
