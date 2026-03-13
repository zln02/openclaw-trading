function scoreColor(score) {
  if (score <= 30) return "#ff4757";
  if (score <= 70) return "#ffa502";
  return "#00d4aa";
}

function polarToCartesian(cx, cy, radius, angle) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(radians),
    y: cy + radius * Math.sin(radians),
  };
}

function describeArc(cx, cy, radius, startAngle, endAngle) {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";

  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

export default function ScoreRadial({ score = 0, label = "Execution Signal" }) {
  const safeScore = Math.max(0, Math.min(100, Number(score) || 0));
  const startAngle = 210;
  const endAngle = -30;
  const totalSweep = 360 - (startAngle - endAngle);
  const sweep = (safeScore / 100) * totalSweep;
  const arcEnd = startAngle + sweep;
  const trackPath = describeArc(120, 120, 84, startAngle, 330);
  const valuePath = safeScore > 0 ? describeArc(120, 120, 84, startAngle, arcEnd) : null;
  const stroke = scoreColor(safeScore);
  const subtitle = safeScore === 0 ? "No Signal" : label;

  return (
    <div className="relative mx-auto h-56 w-full max-w-[260px]">
      <svg viewBox="0 0 240 240" className="h-full w-full overflow-visible">
        <path
          d={trackPath}
          fill="none"
          stroke={safeScore === 0 ? "#1a1a28" : "rgba(255,255,255,0.08)"}
          strokeWidth="18"
          strokeLinecap="round"
        />
        {valuePath ? (
          <path
            d={valuePath}
            fill="none"
            stroke={stroke}
            strokeWidth="18"
            strokeLinecap="round"
            style={{
              filter: `drop-shadow(0 0 12px ${stroke}44)`,
            }}
          />
        ) : null}
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div className="numeric text-4xl font-bold text-[color:var(--text-primary)]">
          {safeScore.toFixed(0)}
        </div>
        <div className="mt-1 text-sm font-semibold text-[color:var(--text-secondary)]">
          {safeScore === 0 ? "No Signal" : label}
        </div>
      </div>
    </div>
  );
}
