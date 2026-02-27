export default function ScoreGauge({ score = 0, label = "복합 스코어", max = 100 }) {
  const pct = Math.min(Math.max(score / max, 0), 1);
  const color =
    score >= 70 ? "text-emerald-400" :
    score >= 50 ? "text-amber-400" :
    score >= 30 ? "text-orange-400" : "text-red-400";
  const bg =
    score >= 70 ? "bg-emerald-400" :
    score >= 50 ? "bg-amber-400" :
    score >= 30 ? "bg-orange-400" : "bg-red-400";

  return (
    <div className="card flex flex-col items-center gap-2 py-6">
      <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
      <div className={`text-4xl font-bold ${color}`}>{score}</div>
      <div className="w-full max-w-[200px] h-2 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${bg}`} style={{ width: `${pct * 100}%` }} />
      </div>
      <span className="text-xs text-gray-600">{max}점 만점</span>
    </div>
  );
}
