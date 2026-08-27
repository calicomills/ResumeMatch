import { DEFAULT_WEIGHTS, type MatchWeights } from "../api";

interface Props {
  weights: MatchWeights;
  onChange: (w: MatchWeights) => void;
  targetCompanies: string;
  onTargetCompaniesChange: (v: string) => void;
  disabled: boolean;
}

const SLIDERS: { key: keyof MatchWeights; label: string }[] = [
  { key: "required", label: "Required skills" },
  { key: "niceToHave", label: "Nice-to-have skills" },
  { key: "experience", label: "Experience" },
  { key: "education", label: "Education" },
  { key: "companies", label: "Target companies" },
];

export function WeightControls({ weights, onChange, targetCompanies, onTargetCompaniesChange, disabled }: Props) {
  const total = Object.values(weights).reduce((a, b) => a + b, 0);

  function setWeight(key: keyof MatchWeights, value: number) {
    onChange({ ...weights, [key]: value });
  }

  return (
    <details className="weight-controls">
      <summary>Scoring weights</summary>
      <div className="weight-controls-body">
        <p className="bulk-hint">
          Control how much each factor counts toward the match score. Adjust to fit what matters
          most for this role.
        </p>

        <div className="weight-sliders">
          {SLIDERS.map(({ key, label }) => {
            const percent = total > 0 ? Math.round((weights[key] / total) * 100) : 0;
            return (
              <label key={key} className="weight-slider">
                <div className="weight-slider-header">
                  <span>{label}</span>
                  <span className="weight-slider-percent">{percent}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={weights[key]}
                  disabled={disabled}
                  onChange={(e) => setWeight(key, Number(e.target.value))}
                />
              </label>
            );
          })}
        </div>

        <label className="weight-companies-field">
          <span>Target companies (comma-separated, optional)</span>
          <input
            type="text"
            placeholder="e.g. Google, Stripe, any Series B+ startup"
            value={targetCompanies}
            disabled={disabled}
            onChange={(e) => onTargetCompaniesChange(e.target.value)}
          />
          <span className="bulk-hint">Only affects scoring if the "Target companies" weight above is non-zero.</span>
        </label>

        <button
          type="button"
          className="text-button"
          disabled={disabled}
          onClick={() => {
            onChange(DEFAULT_WEIGHTS);
            onTargetCompaniesChange("");
          }}
        >
          Reset to defaults
        </button>
      </div>
    </details>
  );
}
