import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import BtcPage from "./pages/BtcPage";
import KrStockPage from "./pages/KrStockPage";
import UsStockPage from "./pages/UsStockPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<BtcPage />} />
          <Route path="/kr" element={<KrStockPage />} />
          <Route path="/us" element={<UsStockPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
