import { useTranslation } from "react-i18next";
import { formatNumber, type Lang } from "../format";
import { CLASSES, type ClassKey } from "../score";

export function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1.5">
      <dt className="text-slate-600">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

export function Disclaimer() {
  const { t } = useTranslation();
  return <p className="rounded bg-amber-50 p-2 text-xs text-amber-900">{t("common.disclaimer")}</p>;
}

export function DemoChip() {
  const { t } = useTranslation();
  return (
    <span className="inline-block rounded bg-red-600 px-2 py-0.5 text-xs font-semibold uppercase text-white">
      {t("common.demoChip")}
    </span>
  );
}

/** Horizontal stacked bar of people per risk class, with the numbers underneath. */
export function PeopleBar({ counts, lang }: { counts: Record<ClassKey, number>; lang: Lang }) {
  const { t } = useTranslation();
  const total = CLASSES.reduce((s, c) => s + (counts[c.key] ?? 0), 0);
  return (
    <div data-testid="people-bar">
      <div className="flex h-4 w-full overflow-hidden rounded border border-slate-200 bg-slate-100">
        {total > 0 &&
          CLASSES.map((c) => (
            <div key={c.key} style={{ width: `${((counts[c.key] ?? 0) / total) * 100}%`, background: c.colour }} />
          ))}
      </div>
      <ul className="mt-1 grid grid-cols-2 gap-x-3 text-xs">
        {CLASSES.map((c) => (
          <li key={c.key} className="flex items-center gap-1.5">
            <span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: c.colour }} />
            <span className="flex-1">{t(`class.${c.key}`)}</span>
            <span className="font-medium">{formatNumber(counts[c.key] ?? 0, lang)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
