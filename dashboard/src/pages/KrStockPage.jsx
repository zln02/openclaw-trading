import { useState } from "react";
import {
  Building2, Wallet, Clock, TrendingUp,
  AlertTriangle, Brain, Target, Layers, ChevronUp, ChevronDown,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip } from "recharts";
import usePolling from "../hooks/usePolling";
import StatCard from "../components/StatCard";
import ScoreGauge from "../components/ScoreGauge";
import TradeTable from "../components/TradeTable";
import { getKrComposite, getKrTrades, getKrSystem, getKrTop, getStockPortfolio } from "../api";

const SECTOR_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

function SectorChart({ positions }) {
  const sectors = {};
  positions.forEach((p) => {
    const s = p.sector || p.industry || "기타";
    sectors[s] = (sectors[s] || 0) + (Number(p.eval_amount || p.evaluation || 0));
  });
  const data = Object.entries(sectors).map(([name, value]) => ({ name, value }));
  if (!data.length) return null;
  return (
    <div className="flex flex-col items-center">
      <p className="text-xs text-text-secondary mb-1">섹터 분포</p>
      <PieChart width={200} height={140}>
        <Pie data={data} cx={100} cy={70} outerRadius={60} dataKey="value" nameKey="name">
          {data.map((_, i) => <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />)}
        </Pie>
        <Tooltip formatter={(v) => `₩${Number(v).toLocaleString()}`} />
      </PieChart>
    </div>
  );
}

const fmt   = (n) => n != null ? Number(n).toLocaleString() : "—";
const pct   = (n) => n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : "—";
const fmtKrw = (n) => n != null ? `₩${Number(n).toLocaleString()}` : "—";

const TRADE_COLS = [
  { key: "created_at", label: "시간",   render: (v) => v?.slice(5, 16) ?? "—" },
  { key: "trade_type", label: "구분",   render: (v) => (
    <span className={v === "BUY" ? "profit-text" : v === "SELL" ? "loss-text" : "text-text-secondary"}>{v}</span>
  )},
  { key: "stock_code", label: "코드",   render: (v, row) => (
    <span className="font-mono text-xs">
      <span className="text-text-primary">{v}</span>
      {row?.stock_name && <span className="text-text-secondary ml-1">{row.stock_name}</span>}
    </span>
  )},
  { key: "price",      label: "가격",   render: (v) => <span className="font-mono">{fmtKrw(v)}</span> },
  { key: "quantity",   label: "수량",   render: (v) => <span className="font-mono">{fmt(v)}</span> },
  { key: "pnl_pct",   label: "수익률",  render: (v) => v != null ? (
    <span className={v > 0 ? "profit-text" : v < 0 ? "loss-text" : "text-text-secondary"}>{pct(v)}</span>
  ) : <span className="text-text-muted">—</span> },
];

function RetBadge({ value, label }) {
  if (value == null) return null;
  const up = value >= 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs ${up ? "profit-text" : "loss-text"}`}>
      {up ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      {label} {pct(value)}
    </span>
  );
}

export default function KrStockPage() {
  const { data: composite, error: compositeError, lastUpdated } = usePolling(getKrComposite, 10000);
  const { data: kiwoom }   = usePolling(getStockPortfolio, 15000);
  const { data: trades }   = usePolling(getKrTrades,       20000);
  const { data: system }   = usePolling(getKrSystem,       30000);
  const { data: topStocks }= usePolling(getKrTop,          60000);
  const [stockFilter, setStockFilter] = useState("");

  // 키움 실시간 포트폴리오 (배너와 동일 데이터)
  const positions   = kiwoom?.positions || [];
  const kiwoomError = kiwoom?.error;

  const trendColor = composite?.trend === "UP"
    ? "profit-text"
    : composite?.trend === "DOWN"
    ? "loss-text"
    : "text-text-secondary";

  return (
    <div className="space-y-6">
      {/* API Error Banner */}
      {compositeError && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          KR 데이터 로드 실패: {compositeError}
        </div>
      )}

      {/* 일일 손실 한도 초과 경고 배너 */}
      {composite?.is_daily_loss_exceeded && (
        <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-red-500/15 border border-red-500/40 text-red-400">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-sm">🚨 일일 손실 한도 초과 — KR 주식 거래 중단</p>
            <p className="text-xs mt-0.5 text-red-400/80">
              오늘 실현 손실: <span className="font-mono font-bold">{composite.daily_loss_pct?.toFixed(2)}%</span>
              &nbsp;/ 한도: <span className="font-mono">{composite.max_daily_loss_pct}%</span>
              &nbsp;· 내일 자정 이후 자동 재개됩니다.
            </p>
          </div>
        </div>
      )}

      {/* 일일 손실 주의 배너 (한도의 75% 이상) */}
      {!composite?.is_daily_loss_exceeded && composite?.daily_loss_pct != null && composite.daily_loss_pct <= composite.max_daily_loss_pct * 0.75 && composite.daily_loss_pct < 0 && (
        <div className="flex items-center gap-3 px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>
            ⚠️ 일일 손실 주의: <span className="font-mono font-semibold">{composite.daily_loss_pct?.toFixed(2)}%</span>
            &nbsp;/ 한도 <span className="font-mono">{composite.max_daily_loss_pct}%</span>
          </span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Building2 className="w-7 h-7 text-blue-400" />
          <h1 className="text-2xl font-bold text-text-primary">KR 주식 대시보드</h1>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-text-secondary">
              마지막 업데이트: {lastUpdated.toLocaleTimeString("ko-KR")}
            </span>
          )}
          {system?.last_cron && (
            <span className="text-xs text-text-secondary flex items-center gap-1 bg-card/50 px-3 py-1 rounded-full border border-border">
              <Clock className="w-3 h-3" /> {system.last_cron}
            </span>
          )}
        </div>
      </div>

      {/* Score Row */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <ScoreGauge score={composite?.total ?? 0} label="KR 종합 점수" />
        <StatCard
          label="시장 추세"
          value={composite?.trend ?? "—"}
          trend={composite?.trend === "UP" ? "up" : composite?.trend === "DOWN" ? "down" : null}
          icon={TrendingUp}
          tooltip="최근 7일 평균 PnL 기반 방향성"
        />
        <StatCard
          label="주간 승률"
          value={composite?.win_rate != null ? `${composite.win_rate}%` : "—"}
          trend={composite?.win_rate > 50 ? "up" : composite?.win_rate < 50 ? "down" : null}
          icon={Target}
          tooltip="최근 7일 체결 기준 승률"
        />
        <StatCard
          label="평균 PnL"
          value={composite?.avg_pnl != null ? pct(composite.avg_pnl) : "—"}
          trend={composite?.avg_pnl > 0 ? "up" : composite?.avg_pnl < 0 ? "down" : null}
          icon={Layers}
          tooltip="최근 7일 평균 거래 수익률"
        />
      </div>

      {/* Portfolio & Top Stocks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Portfolio Summary — 키움 실시간 */}
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Wallet className="w-4 h-4" /> 포트폴리오 요약
            </h3>
            {kiwoom?.is_market_open != null && (
              <span className={`text-xs px-2 py-0.5 rounded-full border ${
                kiwoom.is_market_open
                  ? "bg-green-500/10 border-green-500/30 text-green-400"
                  : "bg-card border-border text-text-muted"
              }`}>
                {kiwoom.is_market_open ? "장중" : "장마감"}
              </span>
            )}
          </div>
          {kiwoomError || !kiwoom ? (
            <div className="py-6 text-center">
              <div className="text-text-secondary text-sm">키움 데이터 로딩 중</div>
              <div className="text-text-muted text-xs mt-1">모의투자 서버 연결 확인 중…</div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-text-secondary mb-1">예수금</div>
                <div className="font-mono font-medium">{fmtKrw(kiwoom.deposit)}</div>
              </div>
              <div>
                <div className="text-text-secondary mb-1">총 평가자산</div>
                <div className="font-mono font-medium">{fmtKrw(kiwoom.estimated_asset)}</div>
              </div>
              <div>
                <div className="text-text-secondary mb-1">누적 손익</div>
                <div className={`font-mono font-medium ${(kiwoom.cumulative_pnl ?? 0) >= 0 ? "profit-text" : "loss-text"}`}>
                  {fmtKrw(kiwoom.cumulative_pnl)}
                  {kiwoom.cumulative_pnl_pct != null && (
                    <span className="text-xs ml-1 opacity-75">({pct(kiwoom.cumulative_pnl_pct)})</span>
                  )}
                </div>
              </div>
              <div>
                <div className="text-text-secondary mb-1">오늘 손익</div>
                <div className={`font-mono font-medium ${(kiwoom.today_pnl ?? 0) >= 0 ? "profit-text" : "loss-text"}`}>
                  {fmtKrw(kiwoom.today_pnl)}
                  {kiwoom.today_pnl_pct != null && kiwoom.today_pnl_pct !== 0 && (
                    <span className="text-xs ml-1 opacity-75">({pct(kiwoom.today_pnl_pct)})</span>
                  )}
                </div>
              </div>
              <div>
                <div className="text-text-secondary mb-1">보유 종목</div>
                <div className="font-mono font-medium">
                  {positions.length}개
                  {kiwoom.max_positions && (
                    <span className="text-text-muted text-xs ml-1">/ {kiwoom.max_positions}개 한도</span>
                  )}
                </div>
              </div>
              <div>
                <div className="text-text-secondary mb-1">총 매입금액</div>
                <div className="font-mono font-medium">{fmtKrw(kiwoom.total_purchase)}</div>
              </div>
            </div>
          )}
        </div>

        {/* Top Stocks */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <TrendingUp className="w-4 h-4" /> TOP 종목 (모멘텀)
            </h3>
          </div>
          <div className="space-y-1.5 max-h-52 overflow-y-auto">
            {(topStocks ?? []).length > 0 ? (
              topStocks.slice(0, 8).map((stock) => (
                <div key={stock.stock_code} className="flex items-center justify-between text-sm px-1 py-0.5 rounded hover:bg-card/30">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-text-secondary w-14">{stock.stock_code}</span>
                    <span className="font-medium text-text-primary truncate max-w-[100px]">{stock.stock_name}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs shrink-0">
                    <span className={`font-mono font-semibold px-1.5 py-0.5 rounded text-xs
                      ${stock.score >= 60 ? "bg-green-500/20 text-green-400" :
                        stock.score <= 40 ? "bg-red-500/20 text-red-400" :
                        "bg-card text-text-secondary"}`}>
                      {stock.score}
                    </span>
                    <RetBadge value={stock.ret_5d}  label="5d" />
                    <RetBadge value={stock.ret_20d} label="20d" />
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-6">
                <div className="text-text-secondary text-sm">장 마감 또는 데이터 수집 중</div>
                <div className="text-text-muted text-xs mt-1">데이터 수집: 매일 08:30 KST</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Sector Distribution + Filter */}
      {positions.length > 0 && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h3 className="text-sm font-medium text-text-primary">섹터 분포 / 종목 검색</h3>
            <input
              type="text"
              placeholder="종목명 또는 코드..."
              value={stockFilter}
              onChange={(e) => setStockFilter(e.target.value)}
              className="text-xs bg-background border border-border rounded px-2 py-1 text-text-primary w-40 focus:outline-none focus:border-blue-500"
            />
          </div>
          <SectorChart positions={positions} />
        </div>
      )}

      {/* Open Positions — 키움 실시간 */}
      {positions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Wallet className="w-4 h-4" /> 보유 포지션 ({positions.length}개)
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  {["종목", "수량", "평균단가", "현재가", "평가금액", "손익금액", "수익률"].map((h) => (
                    <th key={h} className={`py-3 px-3 text-xs text-text-secondary font-medium uppercase tracking-wide ${h === "종목" ? "text-left" : "text-right"}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((pos) => (
                  <tr key={pos.code} className="border-b border-border/50 hover:bg-card/30 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-mono text-xs font-medium">{pos.code?.replace(/^A/, "")}</div>
                      <div className="text-text-secondary text-xs">{pos.name}</div>
                    </td>
                    <td className="text-right py-3 px-3 font-mono">{fmt(pos.quantity)}</td>
                    <td className="text-right py-3 px-3 font-mono">{fmtKrw(pos.avg_entry)}</td>
                    <td className="text-right py-3 px-3 font-mono">{fmtKrw(pos.current_price)}</td>
                    <td className="text-right py-3 px-3 font-mono">{fmtKrw(pos.evaluation)}</td>
                    <td className={`text-right py-3 px-3 font-mono ${(pos.pnl_amount ?? 0) >= 0 ? "profit-text" : "loss-text"}`}>
                      {fmtKrw(pos.pnl_amount)}
                    </td>
                    <td className={`text-right py-3 px-3 font-mono font-semibold ${(pos.pnl_pct ?? 0) >= 0 ? "profit-text" : "loss-text"}`}>
                      {pct(pos.pnl_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* System Status */}
      {system && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary">시스템 상태</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="CPU"    value={`${system.cpu ?? 0}%`}      size="compact" tooltip="시스템 CPU 사용률" />
            <StatCard label="메모리"  value={`${system.mem_pct ?? 0}%`}  size="compact" tooltip="시스템 메모리 사용률" />
            <StatCard label="디스크"  value={`${system.disk_pct ?? 0}%`} size="compact" tooltip="디스크 사용률" />
            <StatCard
              label="키움 연동"
              value={system.kiwoom_ok ? "정상" : "대기"}
              trend={system.kiwoom_ok ? "up" : "warning"}
              size="compact"
              tooltip="키움증권 API 연결 상태 (모의투자)"
            />
          </div>
        </div>
      )}

      {/* Recent Trades */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
            <Brain className="w-4 h-4" /> 최근 거래 기록
          </h3>
          {composite?.n_trades != null && (
            <span className="text-xs text-text-secondary bg-card px-2 py-0.5 rounded-full border border-border">
              최근 7일 {composite.n_trades}건
            </span>
          )}
        </div>
        <TradeTable trades={trades?.slice(0, 15) || []} columns={TRADE_COLS} />
      </div>
    </div>
  );
}
