import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { vectorUrl } from "../api/client";
import { formatNumber, type Lang } from "../format";
import { CLASS_KEYS, type ClassKey } from "../score";
import { useApp } from "../store";
import { DemoChip, Disclaimer, PeopleBar, Row } from "./common";

/** Union statistics come precomputed in the unions GeoJSON properties (pipeline `context`/`demo`). */
export default function UnionPanel({ index }: { index: number }) {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "bn" ? "bn" : "en") as Lang;
  const site = useApp((s) => s.site);
  const q = useQuery({
    queryKey: ["vector", site, "unions"],
    queryFn: async () => (await fetch(vectorUrl(site!, "unions"))).json() as Promise<GeoJSON.FeatureCollection>,
    enabled: !!site,
    staleTime: Infinity,
  });
  const p = q.data?.features[index]?.properties;
  if (!p) return <div className="h-32 animate-pulse rounded bg-slate-100" />;
  const n = (v: unknown, d = 0) => formatNumber(typeof v === "number" ? v : null, lang, { decimals: d });
  const people = Object.fromEntries(CLASS_KEYS.map((k) => [k, Number(p[`people_${k}`] ?? 0)])) as Record<ClassKey, number>;

  return (
    <div className="space-y-3" data-testid="union-panel">
      {p.synthetic && <DemoChip />}
      <h3 className="text-lg font-semibold">{String(p[`name_${lang}`] ?? p.name_en)}</h3>
      <dl className="divide-y divide-slate-100 text-sm">
        <Row label={t("union.landArea")} value={t("polygon.km2", { v: n(p.land_area_km2, 1) })} />
        <Row label={t("union.meanScore")} value={n(p.mean_score)} />
        <Row label={t("union.landLost")} value={t("polygon.km2yr", { v: n(p.area_lost_km2_per_yr, 3) })} />
        <Row label={t("union.buildings")} value={n(p.buildings_total)} />
      </dl>
      <section>
        <h4 className="mb-1 text-sm font-semibold">{t("union.people")}</h4>
        <PeopleBar counts={people} lang={lang} />
      </section>
      <Disclaimer />
    </div>
  );
}
