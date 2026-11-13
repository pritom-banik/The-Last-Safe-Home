import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useApp } from "../store";
import PointCard from "./PointCard";
import PolygonPanel from "./PolygonPanel";
import UnionPanel from "./UnionPanel";

/**
 * Right drawer (380 px) holding the point card, polygon panel or union stats; full screen below 1024 px.
 * Esc closes it. Focus moves into it when it opens and back to where it was when it closes.
 */
export default function Drawer() {
  const { t } = useTranslation();
  const drawer = useApp((s) => s.drawer);
  const close = useApp((s) => s.closeDrawer);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const kind = drawer?.kind;

  useEffect(() => {
    if (!kind) return;
    const before = document.activeElement as HTMLElement | null;
    // keep map clicks on the map (inspecting several points in a row); keyboard users land in the drawer
    if (before && before !== document.body && !before.classList.contains("maplibregl-canvas")) {
      closeBtn.current?.focus({ preventScroll: true });
    }
    return () => {
      if (before && document.contains(before) && before !== document.body) before.focus({ preventScroll: true });
    };
  }, [kind]);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer, close]);

  if (!drawer) return null;
  const title =
    drawer.kind === "point" ? t("point.title") : drawer.kind === "polygon" ? t("polygon.title") : t("union.title");

  return (
    <aside
      className="fixed inset-0 z-40 flex flex-col bg-white lg:absolute lg:inset-y-0 lg:left-auto lg:right-0 lg:z-20 lg:w-[380px] lg:border-l lg:border-slate-200 lg:shadow-xl"
      aria-label={title}
      data-testid="drawer"
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-base font-semibold">{title}</h2>
        <button
          ref={closeBtn}
          type="button"
          onClick={close}
          aria-label={t("point.close")}
          className="flex h-10 w-10 items-center justify-center rounded text-2xl leading-none text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        >
          ×
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {drawer.kind === "point" && <PointCard />}
        {drawer.kind === "polygon" && <PolygonPanel />}
        {drawer.kind === "union" && <UnionPanel index={drawer.index} />}
      </div>
    </aside>
  );
}
