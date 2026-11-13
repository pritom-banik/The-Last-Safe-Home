/** Two-way sync between the zustand store and the URL query (SPEC §10.1). */

import { useEffect } from "react";
import { applyLang, storedLang } from "./i18n";
import { DEFAULT_VISIBLE, isLayerId } from "./map/layerDefs";
import { routeOf } from "./router";
import { useApp } from "./store";
import { decodeUrlState, encodeUrlState, type UrlState } from "./urlState";

/**
 * Seed the store from the URL once, before the first render. On the map page the whole view state comes
 * from the URL; on the other pages only the language and site.
 */
export function initFromUrl(search = window.location.search, pathname = window.location.pathname): UrlState {
  const u = decodeUrlState(search);
  const s = useApp.getState();
  const lang = u.lang ?? storedLang() ?? "en";
  s.setLang(lang);
  applyLang(lang);
  if (u.site) useApp.setState({ site: u.site });
  if (routeOf(pathname) !== "map") return u;
  if (u.lat != null && u.lon != null) s.requestView({ lat: u.lat, lon: u.lon, z: u.z ?? 12 });
  useApp.setState({ visible: u.layers ? u.layers.filter(isLayerId) : DEFAULT_VISIBLE });
  if (u.date) s.setDate(u.date);
  if (u.pt) s.inspect(u.pt);
  if (u.mode) s.setMode(u.mode);
  return u;
}

export function currentUrlState(): UrlState {
  const s = useApp.getState();
  return {
    site: s.site ?? undefined,
    lat: s.view?.lat,
    lon: s.view?.lon,
    z: s.view?.z,
    layers: s.visible,
    date: s.date ?? undefined,
    lang: s.lang,
    mode: s.mode ?? undefined,
    pt: s.point ?? undefined,
  };
}

/** Path + query that reopens the current map view (used by "back to the map" links). */
export function mapPath(): string {
  const qs = encodeUrlState(currentUrlState());
  return `/map${qs ? `?${qs}` : ""}`;
}

/** Query for the current page: the full view on the map; the other pages keep their own parameters. */
function queryFor(pathname: string): string {
  const route = routeOf(pathname);
  if (route === "map") return encodeUrlState(currentUrlState());
  const s = useApp.getState();
  const q = new URLSearchParams(window.location.search);
  if (route !== "report" && route !== "home" && s.site) q.set("site", s.site);
  q.set("lang", s.lang);
  return q.toString().replace(/%2C/g, ",");
}

/** Keep the language applied and the address bar current (replaceState: map moves do not flood history). */
export function useUrlSync(): void {
  useEffect(() => {
    let timer = 0;
    const write = () => {
      const { pathname } = window.location;
      const qs = queryFor(pathname);
      const url = `${pathname}${qs ? `?${qs}` : ""}`;
      if (url !== `${pathname}${window.location.search}`) window.history.replaceState(null, "", url);
    };
    const unsub = useApp.subscribe((s, prev) => {
      if (s.lang !== prev.lang) applyLang(s.lang);
      window.clearTimeout(timer);
      timer = window.setTimeout(write, 150);
    });
    return () => {
      unsub();
      window.clearTimeout(timer);
    };
  }, []);
}
