import Badge from "../../../components/ui/Badge";
import { EmptyState, ErrorState } from "../../../components/ui/PageState";
import { compactTime, krw, pct } from "../../../lib/format";
import { useProData } from "../ProDataContext";

function normalizeAction(action) {
  return String(action || "HOLD").toUpperCase();
}

function actionVariant(action) {
  const a = normalizeAction(action);
  if (a === "BUY") return "buy";
  if (a === "SELL") return "sell";
  return "hold";
}

function tradePnl(trade) {
  if (trade?.pnl_pct != null) return Number(trade.pnl_pct);
  if (trade?.return_pct != null) return Number(trade.return_pct);
  return 0;
}

export default function TradesPanel() {
  const { trades } = useProData();
  const rows = trades?.data?.trades || trades?.data || [];

  if (trades?.error) {
    return (
      <div className="p-3">
        <ErrorState message={`체결 내역 로딩 실패: ${trades.error}`} />
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="p-3">
        <EmptyState message="최근 체결 내역이 없습니다" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto bg-[color:var(--bg-primary)] p-3 scrollbar-subtle">
      <table className="terminal-table w-full">
        <thead>
          <tr>
            <th>시각</th>
            <th>액션</th>
            <th>가격</th>
            <th>손익</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((trade, index) => {
            const action = normalizeAction(trade.action || trade.trade_type || "HOLD");
            const pnl = tradePnl(trade);
            return (
              <tr key={trade.id || index}>
                <td className="numeric text-[color:var(--text-secondary)]">
                  {compactTime(trade.created_at || trade.timestamp)}
                </td>
                <td>
                  <Badge variant={actionVariant(action)}>{action}</Badge>
                </td>
                <td className="numeric">{krw(trade.price || trade.entry_price)}</td>
                <td
                  className={`numeric ${
                    pnl >= 0
                      ? "text-[color:var(--color-profit)]"
                      : "text-[color:var(--color-loss)]"
                  }`}
                >
                  {pct(pnl)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
