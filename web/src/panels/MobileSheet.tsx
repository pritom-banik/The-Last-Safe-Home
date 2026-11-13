/**
 * Mobile (< 1024 px) replacement for the sidebar (SPEC §10.2): a bottom sheet with two tabs, Layers · Summary.
 * Tapping the open tab again (or the handle) folds the sheet so the map gets the whole screen.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { LayersManifest, SiteStats } from "../api/client";
import { LayerList, SiteSummary } from "./Sidebar";

type Tab = "layers" | "summary";

export default function MobileSheet({ manifest, stats, statsError }: { manifest?: LayersManifest; stats?: SiteStats; statsError?: boolean }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab | null>(null);
  const tabs: [Tab, string][] = [
    ["layers", t("sidebar.layers")],
    ["summary", t("sidebar.summary")],
  ];

  return (
    <section
      className="shrink-0 border-t border-slate-200 bg-white shadow-[0_-4px_12px_rgba(15,23,42,0.08)]"
      aria-label={t("sidebar.sheet")}
      data-testid="mobile-sheet"
    >
      <div role="tablist" aria-label={t("sidebar.sheet")} className="flex">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`sheet-tab-${key}`}
            aria-selected={tab === key}
            aria-controls="sheet-panel"
            onClick={() => setTab(tab === key ? null : key)}
            className={`flex min-h-[44px] flex-1 items-center justify-center gap-1.5 text-sm font-semibold ${
              tab === key ? "border-b-2 border-slate-900 text-slate-900" : "text-slate-600"
            }`}
            data-testid={`sheet-tab-${key}`}
          >
            {label}
            <svg viewBox="0 0 12 12" className={`h-3 w-3 transition-transform ${tab === key ? "rotate-180" : ""}`} aria-hidden>
              <path d="M2 8l4-4 4 4" fill="none" stroke="currentColor" strokeWidth="1.8" />
            </svg>
          </button>
        ))}
      </div>
      {tab && (
        <div
          id="sheet-panel"
          role="tabpanel"
          aria-labelledby={`sheet-tab-${tab}`}
          className="max-h-[45vh] overflow-y-auto overscroll-contain border-t border-slate-100 p-4"
        >
          {tab === "layers" ? <LayerList manifest={manifest} /> : <SiteSummary stats={stats} error={statsError} />}
        </div>
      )}
    </section>
  );
}
