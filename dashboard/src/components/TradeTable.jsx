export default function TradeTable({ trades = [], columns = [] }) {
  if (!trades.length) {
    return <div className="card text-sm text-gray-500 text-center py-8">거래 내역 없음</div>;
  }

  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800">
            {columns.map((col) => (
              <th key={col.key} className="text-left py-2 px-2 text-xs text-gray-500 font-medium uppercase">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.map((row, i) => (
            <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
              {columns.map((col) => (
                <td key={col.key} className="py-2 px-2 whitespace-nowrap">
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
