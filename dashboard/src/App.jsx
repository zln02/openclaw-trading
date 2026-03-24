import { Suspense, lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { PortfolioProvider } from "./context/PortfolioContext";

const BtcPage = lazy(() => import("./pages/BtcPage"));
const KrStockPage = lazy(() => import("./pages/KrStockPage"));
const UsStockPage = lazy(() => import("./pages/UsStockPage"));
const AgentsPage = lazy(() => import("./pages/AgentsPage"));

function RouteSkeleton() {
  return (
    <div className="rounded-[var(--panel-radius)] border border-white/10 bg-white/[0.02] p-6 shadow-[var(--shadow-panel)]">
      <div className="h-6 w-40 animate-pulse rounded-full bg-white/10" />
      <div className="mt-4 h-[360px] animate-pulse rounded-[var(--panel-radius-sm)] bg-white/[0.04]" />
    </div>
  );
}

export default function App() {
  return (
    <PortfolioProvider>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route
            index
            element={
              <Suspense fallback={<RouteSkeleton />}>
                <BtcPage />
              </Suspense>
            }
          />
          <Route
            path="/kr"
            element={
              <Suspense fallback={<RouteSkeleton />}>
                <KrStockPage />
              </Suspense>
            }
          />
          <Route
            path="/us"
            element={
              <Suspense fallback={<RouteSkeleton />}>
                <UsStockPage />
              </Suspense>
            }
          />
          <Route
            path="/agents"
            element={
              <Suspense fallback={<RouteSkeleton />}>
                <AgentsPage />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
    </PortfolioProvider>
  );
}
