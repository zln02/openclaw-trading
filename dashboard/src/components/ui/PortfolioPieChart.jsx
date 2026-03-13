import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const FALLBACK_COLORS = [
  "#f7931a",
  "#00d4aa",
  "#3b82f6",
  "#8ea6ff",
  "#ffa502",
  "#ff6b81",
];

export default function PortfolioPieChart({ data = [] }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,220px)_1fr]">
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={68}
              outerRadius={94}
              paddingAngle={2}
              stroke="rgba(255,255,255,0.06)"
              strokeWidth={1}
            >
              {data.map((entry, index) => (
                <Cell key={entry.name || index} fill={entry.color || FALLBACK_COLORS[index % FALLBACK_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value) => [Number(value).toLocaleString(), "Value"]}
              contentStyle={{
                background: "rgba(18,18,26,0.96)",
                border: "1px solid var(--border-default)",
                borderRadius: "12px",
                color: "var(--text-primary)",
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-3">
        {data.map((entry, index) => (
          <div
            key={entry.name || index}
            className="flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2"
          >
            <div className="flex items-center gap-3">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: entry.color || FALLBACK_COLORS[index % FALLBACK_COLORS.length] }}
              />
              <div>
                <div className="text-sm font-medium text-[color:var(--text-primary)]">{entry.name}</div>
                {entry.subtitle ? (
                  <div className="text-xs text-[color:var(--text-muted)]">{entry.subtitle}</div>
                ) : null}
              </div>
            </div>
            <div className="text-right">
              <div className="numeric text-sm text-[color:var(--text-primary)]">
                {entry.displayValue || Number(entry.value || 0).toLocaleString()}
              </div>
              {entry.share != null ? (
                <div className="text-xs text-[color:var(--text-secondary)]">{entry.share}</div>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
