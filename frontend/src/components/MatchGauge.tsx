const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function MatchGauge({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const color = clamped >= 75 ? "var(--good)" : clamped >= 50 ? "var(--warn)" : "var(--bad)";
  const filled = (clamped / 100) * CIRCUMFERENCE;

  return (
    <div className="match-gauge">
      <svg viewBox="0 0 120 120" width="150" height="150">
        <circle cx="60" cy="60" r={RADIUS} className="gauge-track" />
        <circle
          cx="60"
          cy="60"
          r={RADIUS}
          className="gauge-fill"
          style={{ stroke: color, strokeDasharray: `${filled} ${CIRCUMFERENCE}` }}
        />
      </svg>
      <div className="gauge-label">
        <span className="gauge-score" style={{ color }}>
          {clamped}%
        </span>
        <span className="gauge-caption">match</span>
      </div>
    </div>
  );
}
