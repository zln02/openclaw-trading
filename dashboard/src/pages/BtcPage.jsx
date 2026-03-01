import { Bitcoin, Gauge, Wallet, Clock, Newspaper, TrendingUp } from "lucide-react";
import usePolling from "../hooks/usePolling";
import StatCard from "../components/StatCard";
import ScoreGauge from "../components/ScoreGauge";
import TradeTable from "../components/TradeTable";
import {
  getBtcComposite,
  getBtcPortfolio,
  getBtcTrades,
  getBtcSystem,
  getBtcRealtimeAlt,
  getBtcRealtimeNews,
  getBtcRealtimeOrderbook,
  getBtcRealtimePrice,
} from "../api";

const fmt = (n) => n != null ? Number(n).toLocaleString() : "—";
const pct = (n) => n != null ? `${Number(n) >= 0 ? "+" : ""}${Number(n).toFixed(2)}%` : "—";

const TRADE_COLS = [
  { key: "timestamp", label: "시간", render: (v) => v?.slice(5, 16) },
  { key: "action", label: "구분", render: (v) => (
    <span className={v === "BUY" ? "profit-text" : v === "SELL" ? "loss-text" : "text-text-secondary"}>{v}</span>
  )},
  { key: "price", label: "가격", render: (v) => <span className="font-mono">₩{fmt(v)}</span> },
  { key: "rsi", label: "RSI" },
  { key: "confidence", label: "신뢰도", render: (v) => v != null ? `${v}%` : "—" },
  { key: "reason", label: "사유", render: (v) => <span className="text-text-secondary text-xs max-w-[200px] truncate block">{v}</span> },
];

const fetchBtcRtPrice = () => getBtcRealtimePrice("KRW-BTC", "btc");
const fetchBtcOrderbook = () => getBtcRealtimeOrderbook("upbit", "KRW-BTC");
const fetchBtcAlt = () => getBtcRealtimeAlt("BTC");
const fetchBtcNews = () => getBtcRealtimeNews("BTC", 10);

export default function BtcPage() {
  const { data: comp } = usePolling(getBtcComposite, 30000);
  const { data: port } = usePolling(getBtcPortfolio, 30000);
  const { data: trades } = usePolling(getBtcTrades, 60000);
  const { data: news } = usePolling(fetchBtcNews, 120000);
  const { data: sys } = usePolling(getBtcSystem, 60000);
  const { data: rtPrice } = usePolling(fetchBtcRtPrice, 5000);
  const { data: orderbook } = usePolling(fetchBtcOrderbook, 5000);
  const { data: alt } = usePolling(fetchBtcAlt, 60000);

  const score = comp?.composite;
  const summary = port?.summary || {};
  const position = (port?.open_positions || [])[0] || null;
  const priceNow = rtPrice?.price;
  const newsRows = Array.isArray(news?.items) ? news.items : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bitcoin className="w-7 h-7 text-amber-400" />
          <h1 className="text-2xl font-bold text-text-primary">BTC 대시보드</h1>
        </div>
        {sys?.last_cron && (
          <span className="text-xs text-text-secondary flex items-center gap-1 bg-card/50 px-3 py-1 rounded-full border border-border">
            <Clock className="w-3 h-3" /> {sys.last_cron}
          </span>
        )}
      </div>

      {/* Main Score & Price Row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <ScoreGauge score={score?.total ?? 0} />
        <StatCard 
          label="현재가" 
          value={`₩${fmt(priceNow)}`} 
          icon={Bitcoin}
          size="large"
          tooltip="실시간 BTC/KRW 가격"
        />
        <StatCard
          label="F&G 공포지수"
          value={comp?.fg_value ?? "—"}
          sub={comp?.fg_value != null ? (comp.fg_value < 30 ? "극공포" : comp.fg_value > 70 ? "탐욕" : "중립") : null}
          trend={comp?.fg_value < 40 ? "down" : comp?.fg_value > 60 ? "up" : null}
          icon={Gauge}
          tooltip="시장 심리 지수 (0-100)"
        />
        <StatCard
          label="1시간 추세"
          value={comp?.trend ?? "—"}
          icon={TrendingUp}
          tooltip="1시간봉 기술적 추세"
        />
        <StatCard
          label="일봉 RSI"
          value={comp?.rsi_d ?? "—"}
          trend={comp?.rsi_d < 40 ? "down" : comp?.rsi_d > 65 ? "up" : null}
          tooltip="상대강도지수 (과매수: >70, 과매도: <30)"
        />
      </div>

      {/* Market Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="호가 스프레드"
          value={orderbook?.spread != null ? fmt(orderbook.spread) : "—"}
          sub={orderbook?.source || null}
          tooltip="매수-매가 호가 차이"
        />
        <StatCard
          label="호가 불균형"
          value={orderbook?.imbalance != null ? orderbook.imbalance : "—"}
          trend={orderbook?.imbalance > 0 ? "up" : orderbook?.imbalance < 0 ? "down" : null}
          tooltip="매수/매도 호가량 불균형"
        />
        <StatCard
          label="검색 트렌드"
          value={alt?.search_trend_7d ?? "—"}
          trend={alt?.search_trend_7d > 60 ? "up" : alt?.search_trend_7d < 30 ? "down" : null}
          tooltip="7일간 구글 검색 트렌드"
        />
        <StatCard
          label="대체데이터 감정"
          value={alt?.sentiment_score ?? "—"}
          trend={alt?.sentiment_score > 0 ? "up" : alt?.sentiment_score < 0 ? "down" : null}
          tooltip="소셜 미디어 감성 분석"
        />
      </div>

      {/* Score Breakdown */}
      {score && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary">복합 스코어 상세</h3>
          </div>
          <div className="grid grid-cols-3 md:grid-cols-9 gap-3">
            {[
              ["F&G", score.fg, "공포지수"],
              ["RSI", score.rsi, "상대강도"],
              ["BB", score.bb, "볼린저밴드"],
              ["Vol", score.vol, "거래량"],
              ["Trend", score.trend, "추세"],
              ["Fund", score.funding, "펀딩"],
              ["LS", score.ls, "롱숏"],
              ["OI", score.oi, "미결제약정"],
              ["Bonus", score.bonus, "보너스"],
            ].map(([k, v, desc]) => (
              <div key={k} className="text-center p-3 bg-card/50 rounded-lg border border-border/50">
                <div className="text-xs text-text-secondary mb-1">{k}</div>
                <div className={`font-bold text-lg font-mono ${
                  v > 0 ? "profit-text" : v < 0 ? "loss-text" : "text-text-secondary"
                }`}>{v ?? 0}</div>
                <div className="text-xs text-text-muted mt-1">{desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Position & News */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Position Card */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Wallet className="w-4 h-4" /> 포지션 정보
            </h3>
          </div>
          {position ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-text-secondary mb-1">진입가</div>
                  <div className="font-mono font-medium">₩{fmt(position.entry_price)}</div>
                </div>
                <div>
                  <div className="text-text-secondary mb-1">수량</div>
                  <div className="font-mono font-medium">{position.quantity} BTC</div>
                </div>
                <div>
                  <div className="text-text-secondary mb-1">투입금</div>
                  <div className="font-mono font-medium">₩{fmt(position.entry_krw)}</div>
                </div>
                {position?.pnl_pct != null && (
                  <div>
                    <div className="text-text-secondary mb-1">수익률</div>
                    <div className={`font-mono font-medium ${
                      position.pnl_pct >= 0 ? "profit-text" : "loss-text"
                    }`}>
                      {pct(position.pnl_pct)}
                    </div>
                  </div>
                )}
              </div>
              <div className="pt-3 border-t border-border text-xs text-text-secondary">
                <div className="flex justify-between">
                  <span>총평가</span>
                  <span className="font-mono">₩{fmt(summary.total_eval)}</span>
                </div>
                <div className="flex justify-between mt-1">
                  <span>미실현 손익</span>
                  <span className={`font-mono ${
                    summary.unrealized_pnl >= 0 ? "profit-text" : "loss-text"
                  }`}>
                    ₩{fmt(summary.unrealized_pnl)}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-text-secondary">포지션 없음 (대기 중)</div>
          )}
        </div>

        {/* News Card */}
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Newspaper className="w-4 h-4" /> 뉴스 감성
            </h3>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {newsRows.length > 0 ? (
              newsRows.slice(0, 8).map((row, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className="text-text-muted mt-0.5">•</span>
                  <span className="text-text-secondary leading-relaxed">{row.headline || row.title}</span>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-text-secondary text-sm">뉴스 데이터 없음</div>
            )}
          </div>
        </div>
      </div>

      {/* System Status */}
      {sys && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-text-primary">시스템 상태</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="CPU"
              value={`${sys.cpu ?? 0}%`}
              size="compact"
              tooltip="시스템 CPU 사용률"
            />
            <StatCard
              label="메모리"
              value={`${sys.mem_pct ?? 0}%`}
              size="compact"
              tooltip="시스템 메모리 사용률"
            />
            <StatCard
              label="디스크"
              value={`${sys.disk_pct ?? 0}%`}
              size="compact"
              tooltip="디스크 사용률"
            />
            <StatCard
              label="업비트 연동"
              value={sys.upbit_ok ? "정상" : "오류"}
              trend={sys.upbit_ok ? "up" : "down"}
              size="compact"
              tooltip="거래소 API 연결 상태"
            />
          </div>
        </div>
      )}

      {/* Recent Trades */}
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-text-primary">최근 거래 기록</h3>
        </div>
        <TradeTable trades={trades || []} columns={TRADE_COLS} />
      </div>
    </div>
  );
}
