import { createContext, useCallback, useContext, useState } from "react";
import ko from "../i18n/ko";

const defaultT = (key) => key;
const LangContext = createContext({ lang: "ko", t: defaultT, toggle: () => {} });

export function LangProvider({ children }) {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem("oc_lang") || "ko"; } catch { return "ko"; }
  });

  const toggle = useCallback(() => {
    setLang((prev) => {
      const next = prev === "ko" ? "en" : "ko";
      try { localStorage.setItem("oc_lang", next); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const t = useCallback(
    (key) => (lang === "ko" ? (ko[key] ?? key) : key),
    [lang],
  );

  return (
    <LangContext.Provider value={{ lang, t, toggle }}>
      {children}
    </LangContext.Provider>
  );
}

export const useLang = () => useContext(LangContext);
