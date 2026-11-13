import { useTranslation } from "react-i18next";

const KEYS = ["nisar", "landsat", "sentinel2", "pc", "osm", "worldpop", "geoboundaries", "esri"] as const;

/** Data credits (SPEC §16 wording for NISAR and Landsat); used on /method, /about and the report. */
export function Credits({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <>
      <ul className={compact ? "list-disc space-y-0 pl-4" : "list-disc space-y-1 pl-5"} data-testid="credits">
        {KEYS.map((k) => (
          <li key={k}>{t(`credits.${k}`)}</li>
        ))}
      </ul>
      <p className={compact ? "mt-1" : "mt-2"}>{t("credits.notEndorsed")}</p>
    </>
  );
}
