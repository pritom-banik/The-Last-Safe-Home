import { useEffect, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useSites } from "../api/hooks";
import TopBar from "../panels/TopBar";
import { Link } from "../router";
import { useApp } from "../store";
import { mapPath } from "../useUrlSync";

/** Top bar + a readable column for the text pages (/method, /about). */
export default function PageShell({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useTranslation();
  const sites = useSites();
  const site = useApp((s) => s.site);

  useEffect(() => {
    document.title = `${title} — ${t("app.name")}`;
    return () => {
      document.title = t("app.name");
    };
  }, [title, t]);

  // a site for the live numbers: the URL's, else manpura, else the first one
  useEffect(() => {
    if (!sites.data?.length) return;
    if (site && sites.data.some((s) => s.id === site)) return;
    useApp.getState().setSite((sites.data.find((s) => s.id === "manpura") ?? sites.data[0]).id);
  }, [sites.data, site]);

  return (
    <div className="flex min-h-full flex-col">
      <TopBar sites={sites.data} />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6 sm:px-6">
        <p className="mb-4 text-sm">
          <Link to={mapPath()} className="text-sky-700 underline">
            ← {t("nav.backToMap")}
          </Link>
        </p>
        {children}
      </main>
    </div>
  );
}
