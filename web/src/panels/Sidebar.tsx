import { useTranslation } from "react-i18next";
import type { LayersManifest, SiteStats } from "../api/client";
import { formatNumber, formatYear, type Lang } from "../format";
import Legend from "../map/Legend";
import { LAYERS, type LayerId } from "../map/layerDefs";
import { useApp } from "../store";

function useLang(): Lang {
  const { i18n } = useTranslation();
  return i18n.language === "bn" ? "bn" : "en";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-slate-50 p-2">
      <dt className="text-xs text-slate-600">{label}</dt>
      <dd className="text-base font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

export function SiteSummary({ stats, error }: { stats: SiteStats | undefined; error?: boolean }) {
  const { t } = useTranslation();
  const lang = useLang();
  if (error) return <p role="alert" className="rounded bg-slate-100 p-3 text-sm">{t("sidebar.statsError")}</p>;
  if (!stats) return <div className="h-32 animate-pulse rounded bg-slate-100" aria-busy="true" aria-label={t("app.loading")} />;
  const lost = stats.land_lost_km2;
  return (
    <section aria-labelledby="summary-h">
      <h2 id="summary-h" className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("sidebar.summary")}
      </h2>
      <dl className="grid grid-cols-2 gap-2">
        <Stat
          label={t("sidebar.landLost", { year: formatYear(lost?.from_year ?? 1988, lang) })}
          value={t("polygon.km2", { v: formatNumber(lost?.eroded, lang, { decimals: 1 }) })}
        />
        <Stat
          label={t("sidebar.landGained", { year: formatYear(lost?.from_year ?? 1988, lang) })}
          value={t("polygon.km2", { v: formatNumber(lost?.accreted, lang, { decimals: 1 }) })}
        />
        <Stat
          label={t("sidebar.meanRetreat")}
          value={t("polygon.mYr", { v: formatNumber(stats.mean_retreat_m_yr, lang, { decimals: 0 }) })}
        />
        <Stat
          label={t("sidebar.maxRetreat")}
          value={t("polygon.mYr", { v: formatNumber(stats.max_retreat_m_yr, lang, { decimals: 0 }) })}
        />
        <Stat label={t("sidebar.buildings500")} value={formatNumber(stats.buildings_within_500m, lang)} />
        <Stat label={t("sidebar.passes")} value={formatNumber(stats.nisar_passes, lang)} />
      </dl>
    </section>
  );
}

function LayerRow({ id, manifest }: { id: LayerId; manifest: LayersManifest }) {
  const { t } = useTranslation();
  const lang = useLang();
  const on = useApp((s) => s.visible.includes(id));
  const opacity = useApp((s) => s.opacity[id]);
  const toggle = useApp((s) => s.toggleLayer);
  const setOpacity = useApp((s) => s.setOpacity);
  const available = id in manifest.rasters || id in manifest.vectors;
  if (!available) return null;
  const motionHidden = id === "motion" && !manifest.motion_usable;
  const name = t(`layers.${id}`);

  return (
    <li className="border-b border-slate-100 py-2 last:border-0">
      <div className="flex items-center gap-2">
        <input
          id={`layer-${id}`}
          type="checkbox"
          className="h-4 w-4 accent-slate-800"
          checked={on && !motionHidden}
          disabled={motionHidden}
          onChange={() => toggle(id)}
        />
        <label htmlFor={`layer-${id}`} className="flex-1 text-sm">
          {name}
        </label>
        {id === "motion" && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-900">
            {t("layers.lowConfidence")}
          </span>
        )}
      </div>
      {motionHidden && <p className="mt-1 text-xs text-slate-600">{t("layers.motionHidden")}</p>}
      {on && !motionHidden && (
        <div className="mt-1.5 space-y-1.5 pl-6">
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(opacity * 100)}
            onChange={(e) => setOpacity(id, Number(e.target.value) / 100)}
            aria-label={t("sidebar.opacity", { layer: name })}
            aria-valuetext={`${formatNumber(opacity * 100, lang)}%`}
            className="w-full accent-slate-700"
          />
          <Legend id={id} manifest={manifest} />
        </div>
      )}
    </li>
  );
}

export function LayerList({ manifest }: { manifest: LayersManifest | undefined }) {
  const { t } = useTranslation();
  const basemap = useApp((s) => s.basemap);
  const setBasemap = useApp((s) => s.setBasemap);
  return (
    <section aria-labelledby="layers-h">
      <h2 id="layers-h" className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-500">
        {t("sidebar.layers")}
      </h2>
      {manifest ? (
        // top of the list = top of the map
        <ul>
          {[...LAYERS].reverse().map((l) => (
            <LayerRow key={l.id} id={l.id} manifest={manifest} />
          ))}
        </ul>
      ) : (
        <div className="h-40 animate-pulse rounded bg-slate-100" />
      )}
      <fieldset className="mt-2 flex items-center gap-3 text-sm">
        <legend className="sr-only">{t("tools.basemap")}</legend>
        <span className="text-slate-600">{t("tools.basemap")}:</span>
        {(["map", "satellite"] as const).map((b) => (
          <label key={b} className="flex items-center gap-1">
            <input type="radio" name="basemap" checked={basemap === b} onChange={() => setBasemap(b)} />
            {t(b === "map" ? "tools.basemapMap" : "tools.basemapSatellite")}
          </label>
        ))}
      </fieldset>
    </section>
  );
}

export default function Sidebar({ manifest, stats, statsError }: { manifest?: LayersManifest; stats?: SiteStats; statsError?: boolean }) {
  const { t } = useTranslation();
  const open = useApp((s) => s.sidebarOpen);
  if (!open) return null;
  return (
    <aside
      id="sidebar"
      aria-label={t("sidebar.label")}
      className="w-80 shrink-0 space-y-4 overflow-y-auto border-r border-slate-200 bg-white p-4"
      data-testid="sidebar"
    >
      <SiteSummary stats={stats} error={statsError} />
      <LayerList manifest={manifest} />
    </aside>
  );
}
