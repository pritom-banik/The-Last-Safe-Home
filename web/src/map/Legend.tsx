import { useTranslation } from "react-i18next";
import type { LayersManifest } from "../api/client";
import { formatNumber, formatPercent, formatYear, type Lang } from "../format";
import { CLASSES } from "../score";
import { RAMPS, TRANSECT_RANGE, WATER_COLOUR, type LayerId } from "./layerDefs";

const gradient = (stops: string[]) => ({ backgroundImage: `linear-gradient(to right, ${stops.join(", ")})` });

function Ramp({ stops, left, right, unit }: { stops: string[]; left: string; right: string; unit?: string }) {
  return (
    <div>
      <div className="h-2.5 w-full rounded-sm border border-slate-300" style={gradient(stops)} />
      <div className="mt-0.5 flex justify-between text-xs text-slate-600">
        <span>{left}</span>
        {unit && <span>{unit}</span>}
        <span>{right}</span>
      </div>
    </div>
  );
}

function Swatch({ colour, label, line, dot }: { colour: string; label: string; line?: boolean; dot?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-700">
      <span
        aria-hidden
        className={dot ? "h-2 w-2 rounded-full" : line ? "h-1 w-5" : "h-3 w-4 rounded-sm"}
        style={{ background: colour, outline: line ? "1px solid #111827" : undefined }}
      />
      <span>{label}</span>
    </div>
  );
}

export default function Legend({ id, manifest }: { id: LayerId; manifest: LayersManifest }) {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "bn" ? "bn" : "en") as Lang;
  const n = (v: number, signed = false) => formatNumber(v, lang, { signed });
  const r = manifest.rasters[id]?.rescale;

  switch (id) {
    case "sar_hh":
      return <Ramp stops={RAMPS.gray} left={n(r?.[0] ?? -25)} right={n(r?.[1] ?? 0)} unit={t("legend.db")} />;
    case "water":
      return <Swatch colour={WATER_COLOUR} label={t("legend.water")} />;
    case "floodfreq":
      return (
        <div>
          <Ramp stops={RAMPS.blues} left={formatPercent(0, lang)} right={formatPercent(1, lang)} />
          <p className="text-xs text-slate-600">{t("legend.floodfreq")}</p>
        </div>
      );
    case "motion":
      return (
        <div>
          <Ramp stops={RAMPS.rdbu} left={n(r?.[0] ?? -30, true)} right={n(r?.[1] ?? 30, true)} />
          <p className="text-xs text-slate-600">{t("legend.motion")}</p>
        </div>
      );
    case "score":
      return (
        <ul className="space-y-0.5">
          {CLASSES.map((c, i) => (
            <li key={c.key}>
              <Swatch
                colour={c.colour}
                label={`${t(`class.${c.key}`)} (${n(c.min)}–${n(CLASSES[i + 1] ? CLASSES[i + 1].min - 1 : 100)})`}
              />
            </li>
          ))}
        </ul>
      );
    case "banklines": {
      const years = manifest.landsat_years;
      return (
        <div className="space-y-1">
          <Ramp
            stops={RAMPS.viridis}
            left={formatYear(years[0] ?? 1988, lang)}
            right={formatYear(years[years.length - 1] ?? 2026, lang)}
          />
          <p className="text-xs text-slate-600">{t("legend.landsatYears")}</p>
          <Swatch colour="#ffffff" line label={t("legend.nisarLine")} />
        </div>
      );
    }
    case "transects":
      return (
        <div>
          <Ramp
            stops={RAMPS.transects}
            left={`${n(-TRANSECT_RANGE, true)} ${t("legend.accretion")}`}
            right={`${n(TRANSECT_RANGE, true)} ${t("legend.erosion")}`}
          />
          <p className="text-xs text-slate-600">{t("legend.transects")}</p>
        </div>
      );
    case "buildings":
      return (
        <div>
          <Swatch colour="#111827" dot label={t("legend.building")} />
          <p className="text-xs text-slate-500">{t("layers.buildingsZoom")}</p>
        </div>
      );
    case "unions":
      return <Swatch colour="#4b5563" line label={t("legend.union")} />;
  }
}
