import { createContext, useCallback, useContext, useMemo, useState } from "react";
import ko from "../i18n/ko";

const STORAGE_KEY = "openclaw_lang";

export const LangContext = createContext(null);

export function LangProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem(STORAGE_KEY) || "ko");

  const toggle = useCallback(() => {
    setLang((prev) => {
      const next = prev === "ko" ? "en" : "ko";
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const t = useCallback(
    (key) => {
      if (lang === "ko") return ko[key] ?? key;
      return key;
    },
    [lang],
  );

  const value = useMemo(() => ({ lang, toggle, t }), [lang, toggle, t]);

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used inside LangProvider");
  return ctx;
}
