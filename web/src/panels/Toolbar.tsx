import { useTranslation } from "react-i18next";
import type { SiteSummary } from "../api/client";
import { useApp, type Tool } from "../store";

const ICONS: Record<Tool | "reset" | "compare", React.ReactNode> = {
  inspect: <path d="M10 2a6 6 0 016 6c0 4.5-6 10-6 10S4 12.5 4 8a6 6 0 016-6zm0 3.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5z" fill="currentColor" />,
  draw: <path d="M3 15l4-11 9 4-5 9z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />,
  compare: <path d="M10 2v16M3 4h5v12H3zM12 4h5v12h-5z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />,
  reset: <path d="M4 10a6 6 0 1 0 2-4.5M4 3v3.5h3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />,
};

/** Tool buttons, top-right of the map: Inspect, Draw area, Compare, Reset view (SPEC §10.2). */
export default function Toolbar({ site }: { site: SiteSummary | undefined }) {
  const { t } = useTranslation();
  const tool = useApp((s) => s.tool);
  const setTool = useApp((s) => s.setTool);
  const mode = useApp((s) => s.mode);
  const drawerOpen = useApp((s) => s.drawer !== null && s.mode !== "compare");

  const btn = (active: boolean) =>
    `flex h-10 w-10 items-center justify-center rounded ${active ? "bg-slate-900 text-white" : "bg-white text-slate-800 hover:bg-slate-100"}`;

  return (
    <div role="toolbar" aria-label={t("tools.label")} className={`absolute top-3 z-10 flex ${drawerOpen ? "right-3 lg:right-[392px]" : "right-3"} flex-col gap-1 rounded-md bg-white p-1 shadow-md`}>
      {(["inspect", "draw"] as const).map((k) => (
        <button
          key={k}
          type="button"
          aria-label={t(`tools.${k}`)}
          title={t(`tools.${k}`)}
          aria-pressed={tool === k && mode !== "compare"}
          onClick={() => setTool(k)}
          className={btn(tool === k && mode !== "compare")}
          data-testid={`tool-${k}`}
        >
          <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden>
            {ICONS[k]}
          </svg>
        </button>
      ))}
      <button
        type="button"
        aria-label={t("tools.compare")}
        title={t("tools.compare")}
        aria-pressed={mode === "compare"}
        onClick={() => useApp.getState().setMode(mode === "compare" ? null : "compare")}
        className={btn(mode === "compare")}
        data-testid="tool-compare"
      >
        <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden>
          {ICONS.compare}
        </svg>
      </button>
      <button
        type="button"
        aria-label={t("tools.reset")}
        title={t("tools.reset")}
        onClick={() => site && useApp.getState().requestView({ lon: site.center[0], lat: site.center[1], z: site.zoom })}
        className={btn(false)}
      >
        <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden>
          {ICONS.reset}
        </svg>
      </button>
    </div>
  );
}
