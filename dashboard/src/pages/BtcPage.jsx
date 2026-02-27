import { Bitcoin, Gauge, Wallet, Clock, Newspaper } from "lucide-react";
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
    <span className={v === "BUY" ? "text-emerald-400 font-medium" : v === "SELL" ? "text-red-400 font-medium" : "text-gray-400"}>{v}</span>
  )},
  { key: "price", label: "가격", render: (v) => `₩${fmt(v)}` },
  { key: "rsi", label: "RSI" },
  { key: "confidence", label: "신뢰도", render: (v) => v != null ? `${v}%` : "—" },
  { key: "reason", label: "사유", render: (v) => <span className="text-gray-400 text-xs max-w-[200px] truncate block">{v}</span> },
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
      <div className="flex items-center gap-3">
        <Bitcoin className="w-7 h-7 text-amber-400" />
        <h1 className="text-xl font-bold">BTC 대시보드</h1>
        {sys?.last_cron && (
          <span className="text-xs text-gray-600 ml-auto flex items-center gap-1">
            <Clock className="w-3 h-3" /> {sys.last_cron}
          </span>
        )}
      </div>

      {/* Score + Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <ScoreGauge score={score?.total ?? 0} />
        <StatCard label="현재가" value={`₩${fmt(priceNow)}`} icon={Bitcoin} />
        <StatCard
          label="F&G"
          value={comp?.fg_value ?? "—"}
          sub={comp?.fg_value != null ? (comp.fg_value < 30 ? "극공포" : comp.fg_value > 70 ? "탐욕" : "중립") : null}
          trend={comp?.fg_value < 40 ? "down" : comp?.fg_value > 60 ? "up" : null}
          icon={Gauge}
        />
        <StatCard label="1h 추세" value={comp?.trend ?? "—"} icon={Gauge} />
        <StatCard
          label="일봉 RSI"
          value={comp?.rsi_d ?? "—"}
          trend={comp?.rsi_d < 40 ? "down" : comp?.rsi_d > 65 ? "up" : null}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label="호가 스프레드"
          value={orderbook?.spread != null ? fmt(orderbook.spread) : "—"}
          sub={orderbook?.source || null}
        />
        <StatCard
          label="호가 불균형"
          value={orderbook?.imbalance != null ? orderbook.imbalance : "—"}
          trend={orderbook?.imbalance > 0 ? "up" : orderbook?.imbalance < 0 ? "down" : null}
        />
        <StatCard
          label="검색 트렌드"
          value={alt?.search_trend_7d ?? "—"}
          trend={alt?.search_trend_7d > 60 ? "up" : alt?.search_trend_7d < 30 ? "down" : null}
        />
        <StatCard
          label="대체데이터 감정"
          value={alt?.sentiment_score ?? "—"}
          trend={alt?.sentiment_score > 0 ? "up" : alt?.sentiment_score < 0 ? "down" : null}
        />
      </div>

      {/* Score breakdown */}
      {score && (
        <div className="card">
          <h3 className="text-sm font-medium text-gray-400 mb-3">스코어 상세</h3>
          <div className="grid grid-cols-3 md:grid-cols-9 gap-2 text-center text-xs">
            {[
              ["F&G", score.fg], ["RSI", score.rsi], ["BB", score.bb],
              ["Vol", score.vol], ["Trend", score.trend], ["Fund", score.funding],
              ["LS", score.ls], ["OI", score.oi], ["Bonus", score.bonus],
            ].map(([k, v]) => (
              <div key={k} className="py-2 bg-gray-800/50 rounded-lg">
                <div className="text-gray-500">{k}</div>
                <div className={`font-bold mt-0.5 ${v > 0 ? "text-emerald-400" : v < 0 ? "text-red-400" : "text-gray-500"}`}>{v ?? 0}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Position */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="card">
          <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
            <Wallet className="w-4 h-4" /> 포지션
          </h3>
          {position ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">진입가</span><span>₩{fmt(position.entry_price)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">수량</span><span>{position.quantity} BTC</span></div>
              <div className="flex justify-between"><span className="text-gray-500">투입금</span><span>₩{fmt(position.entry_krw)}</span></div>
              {position?.pnl_pct != null && (
                <div className="flex justify-between">
                  <span className="text-gray-500">수익률</span>
                  <span className={position.pnl_pct >= 0 ? "text-emerald-400 font-medium" : "text-red-400 font-medium"}>
                    {pct(position.pnl_pct)}
                  </span>
                </div>
              )}
              <div className="pt-1 border-t border-gray-800/70 text-xs text-gray-500">
                총평가: ₩{fmt(summary.total_eval)} · 미실현: ₩{fmt(summary.unrealized_pnl)}
              </div>
            </div>
          ) : (
            <div className="text-gray-600 text-sm">포지션 없음 (대기 중)</div>
          )}
        </div>

        {/* News */}
        <div className="card">
          <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
            <Newspaper className="w-4 h-4" /> 뉴스 감정
          </h3>
          <ul className="space-y-1 text-xs text-gray-400 max-h-32 overflow-y-auto">
            {newsRows.slice(0, 5).map((row, i) => (
              <li key={i} className="truncate">• {row.headline || row.title}</li>
            ))}
          </ul>
        </div>
      </div>

      {/* System */}
      {sys && (
        <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
          <StatCard label="CPU" value={`${sys.cpu ?? 0}%`} />
          <StatCard label="메모리" value={`${sys.mem_pct ?? 0}%`} />
          <StatCard label="디스크" value={`${sys.disk_pct ?? 0}%`} />
          <StatCard label="거래소 연동" value={sys.upbit_ok ? "정상" : "오류"} trend={sys.upbit_ok ? "up" : "down"} />
        </div>
      )}

      {/* Trades */}
      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-3">최근 거래</h3>
        <TradeTable trades={trades || []} columns={TRADE_COLS} />
      </div>
    </div>
  );
}
