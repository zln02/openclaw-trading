import { Bot, TrendingUp, TrendingDown, Minus, Clock, AlertTriangle } from "lucide-react";
import PropTypes from "prop-types";
import { useMemo } from "react";
import { getAgentDecisions } from "../api";
import usePolling from "../hooks/usePolling";

const MARKET_LABEL = { btc: "BTC", kr: "KR 주식", us: "US 주식" };

function DecisionBadge({ decision }) {
  const d = String(decision || "").toUpperCase();
  if (d === "BUY") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-500/20 text-green-400">
        <TrendingUp className="w-3 h-3" /> BUY
      </span>
    );
  }
  if (d === "SELL") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-500/20 text-red-400">
        <TrendingDown className="w-3 h-3" /> SELL
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/20 text-yellow-400">
      <Minus className="w-3 h-3" /> HOLD
    </span>
  );
}

DecisionBadge.propTypes = {
  decision: PropTypes.string,
};

function LatestCard({ market, decisions }) {
  const latest = decisions.find((d) => d.market === market);
  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-text-primary">
          {MARKET_LABEL[market] ?? market}
        </span>
        {latest ? (
          <DecisionBadge decision={latest.decision} />
        ) : (
          <span className="text-xs text-text-secondary">데이터 없음</span>
        )}
      </div>
      {latest && (
        <>
          <div className="text-xs text-text-secondary">
            확신도 <span className="text-text-primary font-mono">{latest.confidence ?? "—"}%</span>
          </div>
          <div className="text-xs text-text-secondary line-clamp-2">{latest.reasoning ?? ""}</div>
          <div className="flex items-center gap-1 text-xs text-text-secondary mt-1">
            <Clock className="w-3 h-3" />
            {latest.created_at ? new Date(latest.created_at).toLocaleString("ko-KR") : "—"}
          </div>
        </>
      )}
    </div>
  );
}

LatestCard.propTypes = {
  market: PropTypes.string.isRequired,
  decisions: PropTypes.arrayOf(PropTypes.object).isRequired,
};

export default function AgentsPage() {
  const { data, error, loading } = usePolling(getAgentDecisions, 30000);
  const decisions = useMemo(() => data?.decisions ?? [], [data]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Bot className="w-7 h-7 text-accent" />
        <h1 className="text-2xl font-bold text-text-primary">AI 에이전트 팀</h1>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          데이터 로드 실패: {error}
        </div>
      )}

      {/* Latest decisions per market */}
      <div>
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">
          최신 결정
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {loading && !data
            ? ["btc", "kr", "us"].map((m) => (
                <div key={m} className="card p-4 animate-pulse h-28 bg-card/50" />
              ))
            : ["btc", "kr", "us"].map((m) => (
                <LatestCard key={m} market={m} decisions={decisions} />
              ))}
        </div>
      </div>

      {/* Decision history table */}
      <div>
        <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">
          결정 이력
        </h2>
        <div className="card overflow-hidden">
          {loading && !data ? (
            <div className="p-8 text-center text-text-secondary text-sm animate-pulse">
              로딩 중…
            </div>
          ) : decisions.length === 0 ? (
            <div className="p-8 text-center text-text-secondary text-sm">결정 이력이 없습니다.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-text-secondary text-xs">
                    <th className="px-4 py-3">시간</th>
                    <th className="px-4 py-3">시장</th>
                    <th className="px-4 py-3">결정</th>
                    <th className="px-4 py-3">확신도</th>
                    <th className="px-4 py-3 max-w-xs">근거</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.map((d, i) => (
                    <tr
                      key={d.id ?? i}
                      className="border-b border-border/50 hover:bg-card/50 transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-text-secondary whitespace-nowrap">
                        {d.created_at ? new Date(d.created_at).toLocaleString("ko-KR") : "—"}
                      </td>
                      <td className="px-4 py-3 text-text-primary">
                        {MARKET_LABEL[d.market] ?? d.market ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <DecisionBadge decision={d.decision} />
                      </td>
                      <td className="px-4 py-3 font-mono text-text-primary">
                        {d.confidence != null ? `${d.confidence}%` : "—"}
                      </td>
                      <td className="px-4 py-3 text-text-secondary text-xs max-w-xs truncate">
                        {d.reasoning ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
