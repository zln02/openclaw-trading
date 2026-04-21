// English translations — Korean-keyed entries mapped to English values.
// English-keyed entries fall back to the key itself (identity), so only
// keys that are written in Korean need explicit mappings here.
const en = {

  // ── Layout / Navigation ──────────────────────────────────────────────────
  // Keys are English → fallback covers them; no entries needed.

  // ── Portfolio Banner ─────────────────────────────────────────────────────
  "투자금":           "Invested",
  "평가금":           "Valuation",
  "미실현 손익":      "Unrealized PnL",
  "가용 KRW":         "Available KRW",
  "스코어 / 임계":    "Score / Threshold",
  "보유 종목":        "Holdings",
  "투자금 (USD)":     "Invested (USD)",
  "평가금 (USD)":     "Valuation (USD)",
  "환율 (USD/KRW)":   "FX Rate (USD/KRW)",
  "오픈 포지션":      "Open Positions",

  // ── BTC Page ─────────────────────────────────────────────────────────────
  "체결 내역":        "Trade History",
  "실행 피드":        "Execution Feed",

  // ── Connection Status ────────────────────────────────────────────────────
  "연결됨":           "Connected",
  "지연 중":          "Stale",
  "연결 끊김":        "Disconnected",
  "연결 상태":        "Connection",
  "Loading dashboard view…": "Loading dashboard view…",

  // ── KR Page ──────────────────────────────────────────────────────────────
  // Keys in ko.js for KR section are all English → fallback covers them.
  // Extra key used in KrStockPage.jsx but absent from ko.js:
  "키움 연결 오프라인 또는 보유 종목 없음": "Kiwoom offline or no holdings",

  // ── US Page ───────────────────────────────────────────────────────────────
  // Keys in ko.js for US section are all English → fallback covers them.

  // ── Agents Page ───────────────────────────────────────────────────────────
  // Keys in ko.js for Agents section are all English → fallback covers them.

  // ── Common ────────────────────────────────────────────────────────────────
  // All common keys are English → fallback covers them.
};

export default en;
