import { createContext, useContext, useEffect, useState } from "react";
import { getBtcPortfolio, getStockPortfolio, getUsPositions } from "../api";

const PortfolioContext = createContext(null);

export function PortfolioProvider({ children }) {
  const [btcPortfolio, setBtcPortfolio] = useState(null);
  const [krPortfolio, setKrPortfolio] = useState(null);
  const [usPortfolio, setUsPortfolio] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);

  useEffect(() => {
    const refresh = async () => {
      const [btc, kr, us] = await Promise.allSettled([
        getBtcPortfolio(),
        getStockPortfolio(),
        getUsPositions(),
      ]);
      if (btc.status === "fulfilled") setBtcPortfolio(btc.value);
      if (kr.status === "fulfilled") setKrPortfolio(kr.value);
      if (us.status === "fulfilled") setUsPortfolio(us.value);
      setUpdatedAt(Date.now());
    };
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <PortfolioContext.Provider value={{ btcPortfolio, krPortfolio, usPortfolio, updatedAt }}>
      {children}
    </PortfolioContext.Provider>
  );
}

export const usePortfolio = () => useContext(PortfolioContext);
