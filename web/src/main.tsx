import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import ErrorBoundary from "./ErrorBoundary";
import "./i18n";
import "./index.css";
import HomePage from "./pages/HomePage";
import { legacyMapPath, useRoute } from "./router";
import { initFromUrl, useUrlSync } from "./useUrlSync";

// the home page is the landing page and ships in the main bundle; the map and the other pages load on demand
const App = lazy(() => import("./App"));
const MethodPage = lazy(() => import("./pages/MethodPage"));
const AboutPage = lazy(() => import("./pages/AboutPage"));
const ReportPage = lazy(() => import("./report/ReportPage"));

// old map links (/?site=…&lat=…) now live at /map
const legacy = legacyMapPath(window.location.pathname, window.location.search);
if (legacy) window.history.replaceState(null, "", legacy);

initFromUrl();

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

function Root() {
  useUrlSync();
  const route = useRoute();
  if (route === "home") return <HomePage />;
  return (
    <Suspense
      fallback={
        <div className="flex h-full flex-col">
          <div className="flex h-14 shrink-0 items-center bg-slate-900 px-4 text-lg font-semibold text-white">The Last Safe Home</div>
          <div className="flex flex-1 items-center justify-center bg-[#f2efe9] text-sm text-slate-600">…</div>
        </div>
      }
    >
      {route === "map" && <App />}
      {route === "method" && <MethodPage />}
      {route === "about" && <AboutPage />}
      {route === "report" && <ReportPage />}
    </Suspense>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Root />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
);
