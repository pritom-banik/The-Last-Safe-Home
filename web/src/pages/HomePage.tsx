/**
 * Home page (/): what The Last Safe Home is, a big Start button into the map (/map), how it works in plain
 * words, screenshots, the data sources and the team. Theme: Bangladesh's rivers and the people on their banks —
 * the flag's green and red, the app's river blue and its four risk-class colours.
 */

import { useEffect, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useStats } from "../api/hooks";
import { REPO_URL } from "../config";
import { formatNumber, type Lang } from "../format";
import { Link } from "../router";
import { CLASSES, classTextColour } from "../score";
import { useApp } from "../store";
import { initFromUrl } from "../useUrlSync";
import RiverScene from "./home/RiverScene";
import { GivesIcon, Logo, RadarIcon, ScoreIcon, SpeedIcon, TakesIcon, UnknownIcon, YearsIcon } from "./home/icons";

const GREEN = "#006a4e";
const RED = "#f42a41";
const SHOT = (name: string) => `${import.meta.env.BASE_URL ?? "/"}home/${name}.webp`;

/** The member list in the order of the team page; roles are translated. */
const MEMBERS = [
  { name: "Pritom Banik", role: "roleLead", colour: GREEN },
  { name: "Arka Braja Prasad Nath", role: "roleDev", colour: RED },
  { name: "Megha Tania", role: "roleDesign", colour: "#2b7bb0" },
  { name: "Enam E Elahi", role: "roleResearch", colour: "#b7791f" },
] as const;

const initials = (name: string) =>
  name
    .split(" ")
    .filter((w) => w.length > 1)
    .slice(0, 2)
    .map((w) => w[0])
    .join("");

/** "Start" link into the map: seeds the map state from its query before the client-side navigation. */
function StartButton({ lang, big = true, light = false }: { lang: Lang; big?: boolean; light?: boolean }) {
  const { t } = useTranslation();
  const qs = `?site=manpura&lang=${lang}`;
  return (
    <Link
      to={`/map${qs}`}
      onClick={() => initFromUrl(qs, "/map")}
      data-testid="home-start"
      className={`group inline-flex items-center justify-center gap-3 rounded-full font-bold shadow-lg transition
        focus-visible:outline focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-amber-300
        ${big ? "px-8 py-4 text-xl sm:px-10 sm:py-5 sm:text-2xl" : "px-6 py-3 text-lg"}
        ${light ? "bg-white text-[#006a4e] hover:bg-amber-50" : "bg-[#f42a41] text-white hover:bg-[#d61f35]"}`}
    >
      {t("home.start")}
      <svg viewBox="0 0 24 24" className="h-6 w-6 transition group-hover:translate-x-1" aria-hidden>
        <path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
    </Link>
  );
}

function Section({ id, title, intro, tone = "sand", children }: {
  id: string; title: string; intro?: string; tone?: "sand" | "white"; children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className={`scroll-mt-4 px-4 py-16 sm:py-20 ${tone === "white" ? "bg-white" : "bg-[#f7f4ee]"}`}>
      <div className="mx-auto max-w-6xl">
        <h2 id={`${id}-h`} className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          {title}
        </h2>
        <div className="mt-3 h-1 w-16 rounded" style={{ background: `linear-gradient(90deg, ${GREEN} 60%, ${RED} 60%)` }} aria-hidden />
        {intro && <p className="mt-4 max-w-3xl text-lg text-slate-700">{intro}</p>}
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

export default function HomePage() {
  const { t } = useTranslation();
  const lang = useApp((s) => s.lang);
  const setLang = useApp((s) => s.setLang);
  const stats = useStats("manpura");
  const h = (k: string) => t(`home.${k}`);

  useEffect(() => {
    document.title = `${t("app.name")} — ${h("question")}`;
    // fetch the map code while people read, so Start opens it at once
    const id = window.setTimeout(() => void import("../App"), 1500);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const s = stats.data;
  const numbers = s
    ? [
        { value: formatNumber(s.land_lost_km2?.eroded, lang, { decimals: 0 }), label: h("numEroded") },
        { value: formatNumber(s.buildings_within_500m, lang), label: h("numBuildings") },
        { value: formatNumber(s.max_retreat_m_yr, lang, { decimals: 0 }), label: h("numFastest") },
        { value: formatNumber(s.nisar_passes, lang), label: h("numPasses") },
      ]
    : null;

  const nav = [
    ["story", h("navStory")],
    ["how", h("navHow")],
    ["features", h("navFeatures")],
    ["data", h("navData")],
    ["team", h("navTeam")],
  ] as const;

  const story = [
    { icon: <GivesIcon />, title: h("givesTitle"), body: h("givesBody"), colour: GREEN },
    { icon: <TakesIcon />, title: h("takesTitle"), body: h("takesBody"), colour: RED },
    { icon: <UnknownIcon />, title: h("unknownTitle"), body: h("unknownBody"), colour: "#334155" },
  ];
  const steps = [
    { icon: <RadarIcon />, title: h("step1Title"), body: h("step1Body") },
    { icon: <YearsIcon />, title: h("step2Title"), body: h("step2Body") },
    { icon: <SpeedIcon />, title: h("step3Title"), body: h("step3Body") },
    { icon: <ScoreIcon />, title: h("step4Title"), body: h("step4Body") },
  ];
  const features = [
    { img: "point-card", title: h("f1Title"), body: h("f1Body") },
    { img: "radar-slider", title: h("f2Title"), body: h("f2Body") },
    { img: "flood-frequency", title: h("f3Title"), body: h("f3Body") },
    { img: "area-statistics", title: h("f4Title"), body: h("f4Body") },
    { img: "compare-1988", title: h("f5Title"), body: h("f5Body") },
    { img: "bangla", title: h("f6Title"), body: h("f6Body") },
  ];
  const sources = ["nisar", "landsat", "s2", "osm", "worldpop", "geob"];

  return (
    <div className="min-h-full bg-[#f7f4ee] text-slate-900" data-testid="home">
      {/* ---------- hero ---------- */}
      <header className="relative isolate flex flex-col overflow-hidden bg-[#0a1730] lg:h-[92vh] lg:max-h-[920px] lg:min-h-[720px]">
        {/* phones: the picture sits under the text; desktop: it fills the hero behind it */}
        <div className="absolute inset-x-0 bottom-0 h-[430px] sm:h-[480px] lg:inset-0 lg:h-full">
          <RiverScene oldBank={h("oldBank")} todayBank={h("todayBank")} title={h("sceneAlt")} />
        </div>
        <div className="pointer-events-none absolute inset-0 hidden bg-gradient-to-r from-[#0a1730]/85 via-[#0a1730]/30 to-transparent lg:block" aria-hidden />

        <div className="relative z-10 mx-auto flex w-full max-w-6xl items-center gap-3 px-4 py-4 text-white">
          <Logo />
          <span className="text-lg font-bold">{t("app.name")}</span>
          <nav aria-label={h("navLabel")} className="ml-auto hidden items-center gap-5 text-sm text-slate-200 lg:flex">
            {nav.map(([id, label]) => (
              <a key={id} href={`#${id}`} className="hover:text-white hover:underline">
                {label}
              </a>
            ))}
            <Link to={`/method?lang=${lang}`} className="hover:text-white hover:underline">
              {t("nav.method")}
            </Link>
          </nav>
          <button
            type="button"
            onClick={() => setLang(lang === "en" ? "bn" : "en")}
            className="ml-auto rounded border border-white/50 px-2.5 py-1 text-sm hover:bg-white/10 lg:ml-2"
            lang={lang === "en" ? "bn" : "en"}
            aria-label={`${t("nav.language")}: ${t("nav.switchTo")}`}
            data-testid="lang-toggle"
          >
            {lang === "en" ? "বাংলা" : "EN"}
          </button>
        </div>

        <div className="relative z-10 mx-auto w-full max-w-6xl flex-1 px-4 pb-[400px] pt-6 sm:pb-[440px] sm:pt-12 lg:pb-16">
          <div className="max-w-xl text-white">
            <p className="inline-block rounded-full bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-amber-200 ring-1 ring-white/20">
              {h("badge")}
            </p>
            <h1 className="mt-5 text-5xl font-extrabold leading-none tracking-tight sm:text-7xl" data-testid="home-title">
              {t("app.name")}
            </h1>
            <p lang="bn" className="mt-3 text-2xl font-semibold text-amber-200 sm:text-3xl">
              {h("nameBn")}
            </p>
            <p className="mt-6 text-2xl font-semibold sm:text-3xl">{h("question")}</p>
            <p className="mt-4 text-base leading-relaxed text-slate-200 sm:text-lg">{h("lead")}</p>
            <div className="mt-8 flex flex-col items-start gap-3">
              <StartButton lang={lang} />
              <p className="pl-2 text-sm text-slate-300">{h("startHint")}</p>
            </div>
          </div>
        </div>
      </header>

      {/* ---------- the river: life, loss, and the missing date ---------- */}
      <Section id="story" title={h("storyTitle")} intro={h("storyIntro")}>
        <div className="grid gap-6 md:grid-cols-3">
          {story.map((c) => (
            <article key={c.title} className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
              <div className="mb-4 inline-flex rounded-xl p-3 text-white" style={{ background: c.colour }}>
                {c.icon}
              </div>
              <h3 className="text-xl font-bold">{c.title}</h3>
              <p className="mt-2 leading-relaxed text-slate-700">{c.body}</p>
            </article>
          ))}
        </div>

        <div className="mt-10 overflow-hidden rounded-2xl bg-[#0f172a] text-white shadow-lg" data-testid="home-numbers">
          <div className="flex items-center gap-3 border-b border-white/10 px-6 py-4">
            <span className="h-3 w-3 rounded-full" style={{ background: RED }} aria-hidden />
            <h3 className="text-lg font-semibold">{h("numbersTitle")}</h3>
          </div>
          <dl className="grid grid-cols-2 gap-px bg-white/10 lg:grid-cols-4">
            {(numbers ?? Array.from({ length: 4 }, () => null)).map((n, i) => (
              <div key={i} className="bg-[#0f172a] px-6 py-6">
                <dt className="sr-only">{n?.label}</dt>
                <dd>
                  <span className="block text-4xl font-extrabold text-amber-300 sm:text-5xl">
                    {n ? n.value : <span className="inline-block h-10 w-20 animate-pulse rounded bg-white/10" />}
                  </span>
                  <span className="mt-2 block text-sm text-slate-300">{n?.label ?? " "}</span>
                </dd>
              </div>
            ))}
          </dl>
          <p className="px-6 py-3 text-xs text-slate-400">{h("numbersNote")}</p>
        </div>
      </Section>

      {/* ---------- how it works ---------- */}
      <Section id="how" title={h("howTitle")} tone="white">
        <ol className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((st, i) => (
            <li key={st.title} className="relative rounded-2xl bg-[#f7f4ee] p-6 ring-1 ring-slate-200">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-full text-lg font-bold text-white" style={{ background: i === 3 ? RED : GREEN }}>
                  {formatNumber(i + 1, lang)}
                </span>
                <span className="text-[#2b7bb0]">{st.icon}</span>
              </div>
              <h3 className="mt-4 text-lg font-bold">{st.title}</h3>
              <p className="mt-2 leading-relaxed text-slate-700">{st.body}</p>
            </li>
          ))}
        </ol>
        <div className="mt-8 flex flex-wrap items-center gap-2 text-sm" aria-label={t("layers.score")}>
          <span className="mr-1 font-semibold">{t("layers.score")}:</span>
          {CLASSES.map((c, i) => (
            <span key={c.key} className="rounded-full px-3 py-1 font-semibold"
              style={{ background: c.colour, color: classTextColour(c.key) }}>
              {formatNumber(c.min, lang)}–{formatNumber(CLASSES[i + 1] ? CLASSES[i + 1].min - 1 : 100, lang)} · {t(`class.${c.key}`)}
            </span>
          ))}
        </div>
      </Section>

      {/* ---------- what you can do: screenshots ---------- */}
      <Section id="features" title={h("featuresTitle")}>
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <figure key={f.img} className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
              <img src={SHOT(f.img)} alt={f.title} loading="lazy" width={960} height={600}
                className="aspect-[16/10] w-full border-b border-slate-200 object-cover object-left-top" />
              <figcaption className="p-5">
                <h3 className="text-lg font-bold">{f.title}</h3>
                <p className="mt-1 text-slate-700">{f.body}</p>
              </figcaption>
            </figure>
          ))}
        </div>
        <div className="mt-10 flex justify-center">
          <StartButton lang={lang} big={false} />
        </div>
      </Section>

      {/* ---------- data sources ---------- */}
      <Section id="data" title={h("dataTitle")} intro={h("dataIntro")} tone="white">
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {sources.map((k, i) => (
            <article key={k} className="rounded-2xl border-l-4 bg-[#f7f4ee] p-5"
              style={{ borderColor: i < 2 ? "#2b7bb0" : i < 3 ? GREEN : "#94a3b8" }}>
              <h3 className="text-lg font-bold">{h(`${k}Name`)}</h3>
              <p className="text-sm text-slate-500">{h(`${k}By`)}</p>
              <dl className="mt-3 space-y-2 text-sm leading-relaxed">
                <div>
                  <dt className="font-semibold text-slate-900">{h("what")}</dt>
                  <dd className="text-slate-700">{h(`${k}What`)}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-900">{h("how")}</dt>
                  <dd className="text-slate-700">{h(`${k}How`)}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
        <p className="mt-8 text-sm text-slate-600">{h("toolsLine")}</p>
      </Section>

      {/* ---------- team ---------- */}
      <section id="team" aria-labelledby="team-h" className="scroll-mt-4 bg-[#0f172a] px-4 py-16 text-white sm:py-20">
        <div className="mx-auto max-w-6xl">
          <h2 id="team-h" className="text-3xl font-extrabold tracking-tight sm:text-4xl" data-testid="home-team">
            {h("teamTitle")}
          </h2>
          <div className="mt-3 h-1 w-16 rounded" style={{ background: `linear-gradient(90deg, ${GREEN} 60%, ${RED} 60%)` }} aria-hidden />
          <p className="mt-4 max-w-3xl text-lg leading-relaxed text-slate-300">{h("teamIntro")}</p>
          <ul className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {MEMBERS.map((m) => (
              <li key={m.name} className="rounded-2xl bg-white/5 p-6 ring-1 ring-white/10">
                <span className="flex h-14 w-14 items-center justify-center rounded-full text-xl font-bold text-white" style={{ background: m.colour }} aria-hidden>
                  {initials(m.name)}
                </span>
                <p className="mt-4 text-lg font-bold">{m.name}</p>
                <p className="mt-1 text-sm text-amber-200">{h(m.role)}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ---------- call to action ---------- */}
      <section className="relative overflow-hidden px-4 py-16 text-white" style={{ background: GREEN }}>
        <div className="absolute -right-24 top-1/2 h-72 w-72 -translate-y-1/2 rounded-full opacity-90" style={{ background: RED }} aria-hidden />
        <div className="relative mx-auto flex max-w-6xl flex-col items-start gap-6 md:flex-row md:items-center md:justify-between">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-extrabold sm:text-4xl">{h("ctaTitle")}</h2>
            <p className="mt-3 text-lg text-emerald-50">{h("ctaBody")}</p>
          </div>
          <StartButton lang={lang} light />
        </div>
      </section>

      {/* ---------- footer ---------- */}
      <footer className="bg-[#0a1730] px-4 py-8 text-sm text-slate-400">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p>{h("footerDisclaimer")}</p>
            <p className="mt-1">{t("credits.nisar")} {h("notEndorsed")}</p>
          </div>
          <nav className="flex shrink-0 gap-4 text-slate-200">
            <Link to={`/method?lang=${lang}`} className="hover:underline">{t("nav.method")}</Link>
            <Link to={`/about?lang=${lang}`} className="hover:underline">{t("nav.about")}</Link>
            <a href={REPO_URL} target="_blank" rel="noreferrer" className="hover:underline">{h("sourceCode")} · MIT</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
