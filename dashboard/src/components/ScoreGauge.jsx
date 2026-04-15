import PropTypes from "prop-types";

export default function ScoreGauge({ score = 0, label = "복합 스코어", max = 100 }) {
  const pct = Math.min(Math.max(score / max, 0), 1);
  const color =
    score >= 70 ? "text-profit" :
    score >= 50 ? "text-amber-400" :
    score >= 30 ? "text-orange-400" : "text-loss";
  const bg =
    score >= 70 ? "bg-profit" :
    score >= 50 ? "bg-amber-400" :
    score >= 30 ? "bg-orange-400" : "bg-loss";

  return (
    <div className="card flex flex-col items-center gap-3 py-6">
      <span className="data-label">{label}</span>
      <div className={`text-4xl font-bold font-mono ${color}`}>{score}</div>
      <div className="w-full max-w-[200px] h-3 bg-card/50 rounded-full overflow-hidden border border-border/50">
        <div className={`h-full rounded-full transition-all duration-700 ${bg}`} style={{ width: `${pct * 100}%` }} />
      </div>
      <span className="text-xs text-text-secondary">{max}점 만점</span>
    </div>
  );
}

ScoreGauge.propTypes = {
  score: PropTypes.number,
  label: PropTypes.string,
  max: PropTypes.number,
};
