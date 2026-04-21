import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ui/ErrorBoundary";
import { useLang } from "./hooks/useLang";

const BtcPage = lazy(() => import("./pages/BtcPage"));
const KrStockPage = lazy(() => import("./pages/KrStockPage"));
const UsStockPage = lazy(() => import("./pages/UsStockPage"));
const AgentsPage = lazy(() => import("./pages/AgentsPage"));

function RouteSkeleton() {
  // RouteSkeleton은 Layout의 Outlet 내부에 렌더되므로 LangProvider 컨텍스트 접근 가능
  const { t } = useLang();
  return (
    <div
      className="glass-card"
      style={{
        minHeight: 420,
        display: "grid",
        placeItems: "center",
        borderRadius: 24,
      }}
    >
      <div className="subtle">{t("Loading dashboard view…")}</div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route
            index
            element={
              <ErrorBoundary>
                <Suspense fallback={<RouteSkeleton />}>
                  <BtcPage />
                </Suspense>
              </ErrorBoundary>
            }
          />
          <Route
            path="/kr"
            element={
              <ErrorBoundary>
                <Suspense fallback={<RouteSkeleton />}>
                  <KrStockPage />
                </Suspense>
              </ErrorBoundary>
            }
          />
          <Route
            path="/us"
            element={
              <ErrorBoundary>
                <Suspense fallback={<RouteSkeleton />}>
                  <UsStockPage />
                </Suspense>
              </ErrorBoundary>
            }
          />
          <Route
            path="/agents"
            element={
              <ErrorBoundary>
                <Suspense fallback={<RouteSkeleton />}>
                  <AgentsPage />
                </Suspense>
              </ErrorBoundary>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
