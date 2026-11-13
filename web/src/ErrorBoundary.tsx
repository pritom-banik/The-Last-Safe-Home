import { Component, type ReactNode } from "react";
import i18n from "./i18n";

/** Last line of defence: a crash shows a plain message and a reload button instead of a blank page. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error(error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="mx-auto mt-16 max-w-md rounded bg-white p-6 text-center shadow">
        <h1 className="mb-2 text-lg font-semibold">{i18n.t("app.crash")}</h1>
        <p className="mb-4 text-sm text-slate-600">{i18n.t("app.crashHelp")}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          {i18n.t("app.reload")}
        </button>
      </div>
    );
  }
}
