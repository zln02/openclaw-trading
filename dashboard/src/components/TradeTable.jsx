import PropTypes from "prop-types";

export default function TradeTable({ trades = [], columns = [] }) {
  if (!trades.length) {
    return <div className="text-center py-8 text-text-secondary text-sm">거래 내역 없음</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th key={col.key} className="text-left py-3 px-3 text-xs text-text-secondary font-medium uppercase tracking-wide">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.map((row, i) => (
            <tr key={i} className="border-b border-border/50 hover:bg-card/30 transition-colors">
              {columns.map((col) => (
                <td key={col.key} className="py-3 px-3 whitespace-nowrap">
                  {col.render ? col.render(row[col.key], row) : row[col.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

TradeTable.propTypes = {
  trades: PropTypes.arrayOf(PropTypes.object),
  columns: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      render: PropTypes.func,
    })
  ),
};
