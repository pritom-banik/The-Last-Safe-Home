import { Suspense, lazy, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { IS_STATIC } from "./api/client";
import { useHealth, useLayers, useSites, useStats } from "./api/hooks";
import Drawer from "./panels/Drawer";
import Sidebar from "./panels/Sidebar";
import TimeSlider from "./panels/TimeSlider";
import Toolbar from "./panels/Toolbar";
import TopBar from "./panels/TopBar";
import MobileSheet from "./panels/MobileSheet";
import { useApp } from "./store";
import { useIsDesktop } from "./useMedia";

const PREFERRED_SITE = "manpura";

// the map code (MapLibre, ~220 kB gzip) is its own chunk: the page shell paints while it downloads
const MapView = lazy(() => import("./map/MapView"));
const CompareView = lazy(() => import("./map/CompareView"));

/** navigator.onLine, kept current (an offline banner explains why tiles and numbers stop loading). */
function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

/** "Waking up the server…" when /health takes longer than 2 s (free tiers sleep, SPEC §10.9). */
function useSlow(pending: boolean, ms = 2000): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!pending) {
      setSlow(false);
      return;
    }
    const id = window.setTimeout(() => setSlow(true), ms);
    return () => window.clearTimeout(id);
  }, [pending, ms]);
  return slow;
}

export default function App() {
  const { t } = useTranslation();
  const health = useHealth();
  const sites = useSites(health.isSuccess);
  const site = useApp((s) => s.site);
  const date = useApp((s) => s.date);
  const mode = useApp((s) => s.mode);
  const layers = useLayers(site);
  const stats = useStats(site);
  const slow = useSlow(health.isPending);
  const desktop = useIsDesktop();
  const online = useOnline();

  // pick a site once the list arrives: URL choice if valid, else manpura, else the first one
  useEffect(() => {
    if (!sites.data?.length) return;
    const ids = sites.data.map((s) => s.id);
    if (site && ids.includes(site)) {
      if (!useApp.getState().view && !useApp.getState().requestedView) {
        const info = sites.data.find((s) => s.id === site)!;
        useApp.getState().requestView({ lon: info.center[0], lat: info.center[1], z: info.zoom });
      }
      return;
    }
    const pick = sites.data.find((s) => s.id === PREFERRED_SITE) ?? sites.data[0];
    useApp.getState().setSite(pick.id);
    useApp.getState().requestView({ lon: pick.center[0], lat: pick.center[1], z: pick.zoom });
  }, [sites.data, site]);

  // default the date to the latest NISAR pass
  useEffect(() => {
    const dates = layers.data?.nisar_dates;
    if (dates?.length && (!date || !dates.includes(date))) useApp.getState().setDate(dates[dates.length - 1]);
  }, [layers.data, date]);

  const siteInfo = sites.data?.find((s) => s.id === site);
  const manifest = layers.data?.site === site ? layers.data : undefined;

  return (
    <div className="flex h-full flex-col">
      <a href="#main" className="sr-only z-50 bg-white px-3 py-2 focus:not-sr-only focus:absolute focus:left-2 focus:top-2">
        {t("app.skip")}
      </a>
      <TopBar sites={sites.data} />
      {manifest?.synthetic && (
        <div role="status" className="shrink-0 bg-red-700 px-4 py-1.5 text-center text-sm font-bold tracking-wide text-white" data-testid="demo-banner">
          {t("app.demoBanner")}
        </div>
      )}
      {IS_STATIC && (
        <div role="status" className="shrink-0 bg-sky-800 px-4 py-1 text-center text-xs text-white" data-testid="static-banner">
          {t("app.staticBanner")}
        </div>
      )}
      {!online && (
        <div role="status" className="shrink-0 bg-slate-800 px-4 py-1.5 text-center text-sm text-white" data-testid="offline-banner">
          {t("app.offline")}
        </div>
      )}
      {(slow || health.isError || (sites.data && !sites.data.length)) && (
        <div role="status" className="flex shrink-0 items-center justify-center gap-3 bg-amber-100 px-4 py-1.5 text-center text-sm text-amber-900" data-testid="server-banner">
          {slow && !health.isError && <span aria-hidden className="h-3 w-3 animate-spin rounded-full border-2 border-amber-700 border-t-transparent" />}
          <span>{health.isError ? t("app.apiDown") : slow ? t("app.waking") : t("app.noSites")}</span>
          {health.isError && (
            <button type="button" onClick={() => void health.refetch()} className="rounded border border-amber-700 px-2 py-0.5 font-semibold">
              {t("app.retry")}
            </button>
          )}
        </div>
      )}
      {layers.isError && !health.isError && (
        <div role="alert" className="flex shrink-0 items-center justify-center gap-3 bg-amber-100 px-4 py-1.5 text-sm text-amber-900">
          <span>{t("app.siteError")}</span>
          <button type="button" onClick={() => void layers.refetch()} className="rounded border border-amber-700 px-2 py-0.5 font-semibold">
            {t("app.retry")}
          </button>
        </div>
      )}
      <main id="main" className="relative flex min-h-0 flex-1">
        {desktop && <Sidebar manifest={manifest} stats={stats.data} statsError={stats.isError} />}
        <div className="relative min-w-0 flex-1">
          <Suspense fallback={<div className="h-full w-full bg-[#f2efe9]" data-testid="map-placeholder" />}>
            <MapView manifest={manifest} />
          </Suspense>
          {site && layers.isPending && (
            <div role="status" className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 rounded bg-white/95 px-3 py-1.5 text-sm shadow" data-testid="map-loading">
              {t("app.loadingSite")}
            </div>
          )}
          {mode === "compare" && manifest && (
            <Suspense fallback={null}>
              <CompareView manifest={manifest} />
            </Suspense>
          )}
          <Toolbar site={siteInfo} />
          {mode !== "compare" && <Drawer />}
        </div>
      </main>
      {!desktop && <MobileSheet manifest={manifest} stats={stats.data} statsError={stats.isError} />}
      {manifest && <TimeSlider dates={manifest.nisar_dates} gaps={manifest.known_gaps} />}
    </div>
  );
}
