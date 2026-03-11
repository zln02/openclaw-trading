import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";

const BtcPage = lazy(() => import("./pages/BtcPage"));
const KrStockPage = lazy(() => import("./pages/KrStockPage"));
const UsStockPage = lazy(() => import("./pages/UsStockPage"));
const AgentsPage = lazy(() => import("./pages/AgentsPage"));

function RouteSkeleton() {
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
      <div className="subtle">Loading dashboard view…</div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
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
  );
}
