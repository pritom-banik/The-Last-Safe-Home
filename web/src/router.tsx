/**
 * Minimal router for the pages (SPEC §10.1): / (home), /map, /method, /about, /report.
 * The map moved from / to /map when the home page was added; old map links (/?site=…&lat=…) are redirected
 * to /map by legacyMapPath() at start-up (docs/DECISIONS.md).
 * History API + a change event; no router library (docs/DECISIONS.md). Paths are relative to Vite's BASE_URL
 * so the app also works under a sub-path (e.g. GitHub Pages).
 */

import { useSyncExternalStore, type AnchorHTMLAttributes, type MouseEvent } from "react";

export type Route = "home" | "map" | "method" | "about" | "report";

const BASE = (import.meta.env.BASE_URL ?? "/").replace(/\/+$/, "");
const EVENT = "lsh:navigate";

function stripBase(pathname: string, base: string): string {
  let p = pathname;
  if (base && p.startsWith(base)) p = p.slice(base.length);
  return p.replace(/\/index\.html$/, "").replace(/\/+$/, "");
}

/** Page for a pathname (BASE stripped); unknown paths show the home page. */
export function routeOf(pathname: string, base = BASE): Route {
  const p = stripBase(pathname, base);
  if (p === "/map") return "map";
  if (p === "/method") return "method";
  if (p === "/about") return "about";
  if (p === "/report") return "report";
  return "home";
}

/** Query keys that only make sense on the map: a root URL carrying any of them is an old map link. */
const MAP_KEYS = ["site", "lat", "lon", "z", "layers", "date", "pt", "mode"];

/**
 * Old map links pointed at the root (/?site=manpura&lat=…). Returns the /map URL (BASE included) they now
 * belong to, or null when the URL is not one of them.
 */
export function legacyMapPath(pathname: string, search: string, base = BASE): string | null {
  if (stripBase(pathname, base) !== "") return null;
  const q = new URLSearchParams(search);
  if (!MAP_KEYS.some((k) => q.has(k))) return null;
  return `${base}/map${search.startsWith("?") ? search : search ? `?${search}` : ""}`;
}

/** Absolute href for an app path ("/method?lang=bn") under BASE. */
export function href(path: string): string {
  return `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

function subscribe(cb: () => void): () => void {
  window.addEventListener("popstate", cb);
  window.addEventListener(EVENT, cb);
  return () => {
    window.removeEventListener("popstate", cb);
    window.removeEventListener(EVENT, cb);
  };
}

export function useRoute(): Route {
  return useSyncExternalStore(subscribe, () => routeOf(window.location.pathname), () => "home");
}

export function navigate(path: string): void {
  window.history.pushState(null, "", href(path));
  window.dispatchEvent(new Event(EVENT));
  window.scrollTo(0, 0);
}

/** In-app link: plain left clicks navigate without a reload; modified clicks open as usual. */
export function Link({ to, onClick, ...rest }: { to: string } & AnchorHTMLAttributes<HTMLAnchorElement>) {
  const handle = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (rest.target && rest.target !== "_self") return;
    e.preventDefault();
    navigate(to);
  };
  return <a href={href(to)} onClick={handle} {...rest} />;
}
