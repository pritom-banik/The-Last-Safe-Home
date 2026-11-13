/** /about (SPEC §10.1): what this is, team, licence, repository, data credits. */

import { useTranslation } from "react-i18next";
import { LOCAL_EVENT, REPO_URL, TEAM, TEAM_NAME } from "../config";
import { Credits } from "./Credits";
import PageShell from "./PageShell";

export default function AboutPage() {
  const { t } = useTranslation();
  return (
    <PageShell title={t("nav.about")}>
      <h1 className="mb-3 text-2xl font-bold">{t("app.name")}</h1>
      <p className="mb-3">{t("about.intro")}</p>
      <p className="mb-6">{t("about.challenge")}</p>

      <section className="mb-6" aria-labelledby="team-h">
        <h2 id="team-h" className="mb-2 text-xl font-semibold">
          {t("about.team")}
        </h2>
        <p className="mb-2" data-testid="team-name">
          {t("about.teamLine", { team: TEAM_NAME, event: LOCAL_EVENT })}
        </p>
        {TEAM.length ? (
          <ul className="list-disc pl-5" data-testid="team">
            {TEAM.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        ) : (
          <p>{t("about.teamText")}</p>
        )}
      </section>

      <section className="mb-6" aria-labelledby="code-h">
        <h2 id="code-h" className="mb-2 text-xl font-semibold">
          {t("about.code")}
        </h2>
        <p>
          {t("about.licence")}{" "}
          <a href={REPO_URL} className="text-sky-700 underline" target="_blank" rel="noreferrer">
            {REPO_URL.replace(/^https:\/\//, "")}
          </a>
        </p>
      </section>

      <section aria-labelledby="credits-h">
        <h2 id="credits-h" className="mb-2 text-xl font-semibold">
          {t("credits.title")}
        </h2>
        <Credits />
      </section>
    </PageShell>
  );
}
