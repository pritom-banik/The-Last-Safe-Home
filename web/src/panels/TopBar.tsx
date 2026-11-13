import { useTranslation } from "react-i18next";
import type { SiteSummary } from "../api/client";
import { Link, useRoute } from "../router";
import { useApp } from "../store";
import { mapPath } from "../useUrlSync";

export default function TopBar({ sites }: { sites: SiteSummary[] | undefined }) {
  const { t } = useTranslation();
  const site = useApp((s) => s.site);
  const lang = useApp((s) => s.lang);
  const setLang = useApp((s) => s.setLang);
  const sidebarOpen = useApp((s) => s.sidebarOpen);
  const setSidebarOpen = useApp((s) => s.setSidebarOpen);
  const route = useRoute();
  const onMap = route === "map";
  const pageQuery = `?${new URLSearchParams({ ...(site ? { site } : {}), lang }).toString()}`;

  const chooseSite = (id: string) => {
    const info = sites?.find((x) => x.id === id);
    useApp.getState().setSite(id);
    if (info) useApp.getState().requestView({ lon: info.center[0], lat: info.center[1], z: info.zoom });
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 bg-slate-900 px-3 text-white">
      {onMap && (
      <button
        // the side panel exists on desktop only; phones use the bottom sheet
        type="button"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label={t("sidebar.toggle")}
        aria-expanded={sidebarOpen}
        aria-controls="sidebar"
        className="hidden rounded p-1.5 hover:bg-slate-700 lg:block"
      >
        <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden>
          <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="2" />
        </svg>
      </button>
      )}
      {/* the name leads to the home page */}
      {onMap ? (
        <h1 className="truncate text-base font-semibold sm:text-lg">
          <Link to={`/?lang=${lang}`} className="hover:underline" data-testid="home-link">
            {t("app.name")}
          </Link>
        </h1>
      ) : (
        <Link to={`/?lang=${lang}`} className="truncate text-lg font-semibold hover:underline" data-testid="home-link">
          {t("app.name")}
        </Link>
      )}
      <span className="hidden truncate text-sm text-slate-300 xl:inline">{t("app.tagline")}</span>
      <div className="ml-auto flex items-center gap-3">
        {sites && sites.length > 0 && (
          <label className="flex items-center gap-1.5 text-sm">
            <span className="hidden sm:inline">{t("nav.site")}</span>
            <select
              aria-label={t("nav.site")}
              value={site ?? ""}
              onChange={(e) => chooseSite(e.target.value)}
              className="max-w-[9rem] rounded bg-slate-800 px-2 py-1 text-sm text-white sm:max-w-none"
              data-testid="site-select"
            >
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name[lang] ?? s.name.en}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          onClick={() => setLang(lang === "en" ? "bn" : "en")}
          className="rounded border border-slate-500 px-2 py-1 text-sm hover:bg-slate-700"
          lang={lang === "en" ? "bn" : "en"}
          aria-label={`${t("nav.language")}: ${t("nav.switchTo")}`}
          data-testid="lang-toggle"
        >
          {lang === "en" ? "বাংলা" : "EN"}
        </button>
        <details className="relative md:hidden" data-testid="nav-menu">
          <summary className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded hover:bg-slate-700" aria-label={t("nav.menu")}>
            <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden>
              <circle cx="10" cy="4" r="1.8" fill="currentColor" />
              <circle cx="10" cy="10" r="1.8" fill="currentColor" />
              <circle cx="10" cy="16" r="1.8" fill="currentColor" />
            </svg>
          </summary>
          <div className="absolute right-0 z-50 mt-1 flex w-40 flex-col rounded bg-white py-1 text-sm text-slate-900 shadow-lg">
            <Link to={`/?lang=${lang}`} className="px-3 py-2.5 hover:bg-slate-100">
              {t("nav.home")}
            </Link>
            {!onMap && (
              <Link to={mapPath()} className="px-3 py-2.5 hover:bg-slate-100">
                {t("nav.map")}
              </Link>
            )}
            <Link to={`/method${pageQuery}`} className="px-3 py-2.5 hover:bg-slate-100">
              {t("nav.method")}
            </Link>
            <Link to={`/about${pageQuery}`} className="px-3 py-2.5 hover:bg-slate-100">
              {t("nav.about")}
            </Link>
          </div>
        </details>
        <nav className="hidden items-center gap-3 text-sm md:flex">
          <Link to={`/?lang=${lang}`} className="hover:underline">
            {t("nav.home")}
          </Link>
          <span aria-hidden>·</span>
          {!onMap && (
            <>
              <Link to={mapPath()} className="hover:underline">
                {t("nav.map")}
              </Link>
              <span aria-hidden>·</span>
            </>
          )}
          <Link to={`/method${pageQuery}`} className="hover:underline" aria-current={route === "method" ? "page" : undefined}>
            {t("nav.method")}
          </Link>
          <span aria-hidden>·</span>
          <Link to={`/about${pageQuery}`} className="hover:underline" aria-current={route === "about" ? "page" : undefined}>
            {t("nav.about")}
          </Link>
        </nav>
      </div>
    </header>
  );
}
