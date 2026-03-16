/**
 * StrategyPanel — 에이전트 전략 현황 카드
 * BTC / KR / US 페이지에서 공통으로 사용
 */
import { Bot, CheckCircle2, XCircle, AlertCircle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import Badge from "./ui/Badge";
import Card from "./ui/Card";
import LoadingSkeleton from "./ui/LoadingSkeleton";
import { pct, num } from "../lib/format";

function ConditionRow({ label, value, pass, warn }) {
  const Icon = pass ? CheckCircle2 : warn ? AlertCircle : XCircle;
  const color = pass
    ? "text-[color:var(--color-profit)]"
    : warn
    ? "text-[color:var(--color-warning)]"
    : "text-[color:var(--color-loss)]";
  return (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-white/[0.04] last:border-0">
      <div className="flex items-center gap-2">
        <Icon size={13} className={`shrink-0 ${color}`} />
        <span className="text-xs text-[color:var(--text-secondary)]">{label}</span>
      </div>
      <span className={`numeric text-xs font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function RegimeBadge({ regime }) {
  const map = {
    BULL: { label: "강세장", variant: "profit" },
    BEAR: { label: "약세장", variant: "loss" },
    TRANSITION: { label: "전환중", variant: "warning" },
    SIDEWAYS: { label: "횡보", variant: "neutral" },
    UPTREND: { label: "상승추세", variant: "profit" },
    DOWNTREND: { label: "하락추세", variant: "loss" },
    CORRECTION: { label: "조정중", variant: "warning" },
    RECOVERY: { label: "회복중", variant: "info" },
    CRISIS: { label: "위기", variant: "loss" },
  };
  const r = map[regime?.toUpperCase()] || { label: regime || "알 수 없음", variant: "neutral" };
  return <Badge variant={r.variant}>{r.label}</Badge>;
}

/* ──────────────────────────────────────────────
   BTC 전략 패널
────────────────────────────────────────────── */
export function BtcStrategyPanel({ composite, filters, decisions, loading }) {
  if (loading) return <LoadingSkeleton height={240} />;

  const score = Number(composite?.composite_score ?? composite?.composite?.total ?? 0);
  const threshold = Number(composite?.buy_threshold ?? 50);
  const regime = composite?.regime || composite?.composite?.regime || "TRANSITION";
  const trend = composite?.trend || "—";
  const rsiVal = Number(composite?.rsi_d ?? 0);
  const fg = Number(composite?.fg_value ?? 0);
  const fundingRate = Number(filters?.funding_rate ?? 0);
  const kimchi = Number(filters?.kimchi_premium ?? 0);
  const kimchiBl = filters?.kimchi_blocked ?? false;
  const fundingBl = filters?.funding_overheated ?? false;
  const todayTrades = Number(filters?.today_trades ?? 0);
  const maxTrades = Number(filters?.max_trades_per_day ?? 2);
  const latestReason = decisions?.[0]?.reason || "판단 근거 없음";
  const latestAction = decisions?.[0]?.action || "HOLD";

  const scorePass = score >= threshold;
  const conditions = [
    { label: `종합 점수 ${score} / 임계값 ${threshold}`, value: `${score}점`, pass: scorePass },
    { label: `RSI (과매도 < 30 유리)`, value: rsiVal.toFixed(1), pass: rsiVal < 65, warn: rsiVal < 40 },
    { label: `공포·탐욕 지수`, value: `${fg} (${fg <= 25 ? "극도공포" : fg <= 45 ? "공포" : fg <= 55 ? "중립" : fg <= 75 ? "탐욕" : "극도탐욕"})`, pass: fg < 70, warn: fg < 45 },
    { label: `김치 프리미엄 차단`, value: `${kimchi.toFixed(2)}%`, pass: !kimchiBl, warn: Math.abs(kimchi) > 1 },
    { label: `펀딩비 과열 차단`, value: `${(fundingRate * 100).toFixed(4)}%`, pass: !fundingBl, warn: fundingRate > 0.01 },
    { label: `오늘 거래 횟수`, value: `${todayTrades} / ${maxTrades}회`, pass: todayTrades < maxTrades, warn: todayTrades >= maxTrades - 1 },
  ];
  const passCount = conditions.filter((c) => c.pass).length;

  return (
    <Card title="에이전트 전략" icon={<Bot size={14} />} delay={8} bodyClassName="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-sm text-[color:var(--text-primary)]">룰기반 복합점수 에이전트</div>
          <div className="mt-1 text-xs text-[color:var(--text-muted)]">
            F&G·RSI·BB·거래량·추세·펀딩·LS·OI·뉴스·고래 10개 신호 가중합산 → {threshold}점 초과 시 매수
          </div>
        </div>
        <div className="shrink-0 text-right space-y-1">
          <RegimeBadge regime={regime} />
          <div className="block">
            <Badge variant={latestAction === "BUY" ? "buy" : latestAction === "SELL" ? "sell" : "hold"}>
              {latestAction}
            </Badge>
          </div>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">진입 조건</span>
          <span className={`text-xs font-semibold ${passCount >= 4 ? "text-[color:var(--color-profit)]" : passCount >= 2 ? "text-[color:var(--color-warning)]" : "text-[color:var(--color-loss)]"}`}>
            {passCount}/{conditions.length} 충족
          </span>
        </div>
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-1">
          {conditions.map((c) => (
            <ConditionRow key={c.label} {...c} />
          ))}
        </div>
      </div>

      <div>
        <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">최근 판단 근거</div>
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 text-sm text-[color:var(--text-secondary)]">
          {latestReason}
        </div>
      </div>
    </Card>
  );
}

/* ──────────────────────────────────────────────
   KR 전략 패널
────────────────────────────────────────────── */
export function KrStrategyPanel({ strategy, account, loading }) {
  if (loading) return <LoadingSkeleton height={240} />;

  const mode = strategy?.mode || "전략 대기";
  const summary = strategy?.summary || "전략 파일이 아직 생성되지 않았습니다.";
  const confidence = Number(strategy?.confidence ?? 0);
  const mlPrediction = Number(strategy?.ml_prediction ?? 50);
  const outlook = strategy?.market_outlook || "중립";
  const riskLevel = strategy?.risk_level || "알 수 없음";
  const picks = strategy?.top_picks || [];
  const buyPicks = picks.filter((p) => p.action === "BUY");
  const watchPicks = picks.filter((p) => p.action === "WATCH");
  const openCount = Number(account?.positions?.length ?? 0);
  const maxPositions = 5;

  const conditions = [
    { label: "장 전 전략 파일", value: strategy?.strategy ? "로드됨" : "미생성", pass: !!strategy?.strategy, warn: !strategy?.strategy },
    { label: `전략 신뢰도 (임계 60%)`, value: `${confidence}%`, pass: confidence >= 60, warn: confidence >= 40 },
    { label: `ML 예측 (강세 > 50)`, value: `${mlPrediction.toFixed(0)}%`, pass: mlPrediction >= 50, warn: mlPrediction >= 45 },
    { label: `보유 포지션`, value: `${openCount} / ${maxPositions}개`, pass: openCount < maxPositions, warn: openCount >= maxPositions - 1 },
    { label: `BUY 후보 종목`, value: `${buyPicks.length}개`, pass: buyPicks.length > 0, warn: buyPicks.length === 0 },
  ];
  const passCount = conditions.filter((c) => c.pass).length;

  return (
    <Card title="에이전트 전략" icon={<Bot size={14} />} delay={4} bodyClassName="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-sm text-[color:var(--text-primary)]">ML 블렌딩 에이전트 (KR)</div>
          <div className="mt-1 text-xs text-[color:var(--text-muted)]">
            룰기반 60% + XGBoost ML 40% 합산 → WATCHLIST 51종목 모멘텀 스크리닝 → 상위 30개 심층 분석
          </div>
        </div>
        <div className="shrink-0 text-right space-y-1">
          <Badge variant="kr">{mode}</Badge>
          <div className="block">
            <Badge variant={outlook === "강세" || outlook === "상승" ? "profit" : outlook === "약세" || outlook === "하락" ? "loss" : "neutral"}>
              {outlook}
            </Badge>
          </div>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">진입 조건</span>
          <span className={`text-xs font-semibold ${passCount >= 4 ? "text-[color:var(--color-profit)]" : passCount >= 2 ? "text-[color:var(--color-warning)]" : "text-[color:var(--color-loss)]"}`}>
            {passCount}/{conditions.length} 충족
          </span>
        </div>
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-1">
          {conditions.map((c) => (
            <ConditionRow key={c.label} {...c} />
          ))}
        </div>
      </div>

      {summary && (
        <div>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">전략 요약</div>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 text-sm text-[color:var(--text-secondary)]">
            {summary}
          </div>
        </div>
      )}

      {(buyPicks.length > 0 || watchPicks.length > 0) && (
        <div>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
            오늘 전략 종목 ({picks.length}개)
          </div>
          <div className="space-y-1">
            {[...buyPicks.slice(0, 3), ...watchPicks.slice(0, 2)].map((p, i) => (
              <div key={p.code || i} className="flex items-center justify-between gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Badge variant={p.action === "BUY" ? "buy" : "warning"} className="shrink-0">{p.action}</Badge>
                  <span className="text-xs font-medium text-[color:var(--text-primary)] truncate">{p.name || p.code}</span>
                </div>
                <span className="numeric text-[11px] text-[color:var(--text-muted)] shrink-0">{p.code}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

/* ──────────────────────────────────────────────
   US 전략 패널
────────────────────────────────────────────── */
export function UsStrategyPanel({ market, positions, loading }) {
  if (loading) return <LoadingSkeleton height={240} />;

  const regime = market?.regime;
  const regimeName = regime?.regime || "알 수 없음";
  const vix = Number(regime?.vix ?? 0);
  const spyAbove200 = regime?.spy_above_200ma ?? false;
  const spyPrice = Number(regime?.spy_price ?? 0);
  const spyMa50 = Number(regime?.spy_ma50 ?? 0);
  const spyMa200 = Number(regime?.spy_ma200 ?? 0);
  const openCount = Number(positions?.summary?.count ?? positions?.positions?.length ?? 0);
  const maxPositions = 10;
  const pnlPct = Number(positions?.summary?.total_pnl_pct ?? 0);

  const indices = market?.indices || [];
  const spx = indices.find((i) => i.name === "S&P 500");
  const vixObj = indices.find((i) => i.name === "VIX");

  const conditions = [
    { label: "SPY 200MA 위 (강세 기본조건)", value: spyAbove200 ? "위" : "아래", pass: spyAbove200 },
    { label: `SPY vs 50MA`, value: spyPrice > 0 && spyMa50 > 0 ? `${(((spyPrice - spyMa50) / spyMa50) * 100).toFixed(1)}%` : "—", pass: spyPrice > spyMa50, warn: Math.abs(spyPrice - spyMa50) / (spyMa50 || 1) < 0.02 },
    { label: `VIX (공포지수 < 20 안전)`, value: vix.toFixed(1), pass: vix < 20, warn: vix < 30 },
    { label: `보유 포지션`, value: `${openCount} / ${maxPositions}개`, pass: openCount < maxPositions, warn: openCount >= maxPositions - 1 },
    { label: `S&P500 일간 변화`, value: spx ? `${spx.change_pct >= 0 ? "+" : ""}${spx.change_pct?.toFixed(2)}%` : "—", pass: (spx?.change_pct ?? 0) >= 0, warn: (spx?.change_pct ?? 0) >= -1 },
  ];
  const passCount = conditions.filter((c) => c.pass).length;

  return (
    <Card title="에이전트 전략" icon={<Bot size={14} />} delay={6} bodyClassName="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-sm text-[color:var(--text-primary)]">모멘텀 에이전트 (US)</div>
          <div className="mt-1 text-xs text-[color:var(--text-muted)]">
            5/20일 수익률·거래량비율·신고가 근접 기반 모멘텀 스코어링 → SPY 200MA 추세 필터 · DRY-RUN 모드
          </div>
        </div>
        <div className="shrink-0 text-right space-y-1">
          <RegimeBadge regime={regimeName} />
          <div className="block">
            <Badge variant="us">DRY-RUN</Badge>
          </div>
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">시장 조건</span>
          <span className={`text-xs font-semibold ${passCount >= 4 ? "text-[color:var(--color-profit)]" : passCount >= 2 ? "text-[color:var(--color-warning)]" : "text-[color:var(--color-loss)]"}`}>
            {passCount}/{conditions.length} 충족
          </span>
        </div>
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-1">
          {conditions.map((c) => (
            <ConditionRow key={c.label} {...c} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "SPY 현재가", value: `$${spyPrice.toFixed(0)}` },
          { label: "SPY 50MA", value: `$${spyMa50.toFixed(0)}` },
          { label: "SPY 200MA", value: `$${spyMa200.toFixed(0)}` },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-2.5 py-2 text-center">
            <div className="text-[10px] text-[color:var(--text-muted)]">{item.label}</div>
            <div className="mt-1 numeric text-xs font-semibold text-[color:var(--text-primary)]">{item.value}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}
