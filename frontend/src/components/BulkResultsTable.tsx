import type { BulkAnalyzeResponse } from "../api";

interface Props {
  result: BulkAnalyzeResponse;
  onViewFull: (filename: string) => void;
}

function scoreClass(score: number | null): string {
  if (score === null) return "";
  if (score >= 75) return "score-good";
  if (score >= 50) return "score-warn";
  return "score-bad";
}

export function BulkResultsTable({ result, onViewFull }: Props) {
  const showCompanies = result.target_companies.length > 0;

  return (
    <div className="bulk-results">
      <div className="bulk-summary-row">
        <span>
          {result.candidates.length} candidate{result.candidates.length === 1 ? "" : "s"} ranked
        </span>
        {result.failed.length > 0 && (
          <span className="bulk-failed-count">{result.failed.length} file(s) could not be read</span>
        )}
      </div>

      <div className="bulk-table-wrap">
        <table className="bulk-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Candidate</th>
              <th>Match</th>
              <th>Required skills</th>
              {showCompanies && <th>Target companies</th>}
              <th>Experience</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {result.candidates.map((c, i) => (
              <tr key={c.filename} className={c.hidden_text_found || c.suspicious_phrases_found ? "row-flagged" : ""}>
                <td>{i + 1}</td>
                <td>
                  <div className="bulk-candidate-name">{c.candidate_name ?? c.filename}</div>
                  <div className="bulk-filename">{c.filename}</div>
                  {(c.hidden_text_found || c.suspicious_phrases_found) && (
                    <div className="bulk-flag">⚠ hidden/manipulative content found</div>
                  )}
                </td>
                <td>
                  <span className={`bulk-score ${scoreClass(c.score)}`}>{c.score}%</span>
                </td>
                <td className="bulk-skills-cell">
                  {c.required_matched.length > 0 && (
                    <span className="bulk-skill-chip bulk-skill-match">{c.required_matched.length} matched</span>
                  )}
                  {c.required_missing.length > 0 && (
                    <span className="bulk-skill-chip bulk-skill-missing" title={c.required_missing.join(", ")}>
                      missing: {c.required_missing.slice(0, 3).join(", ")}
                      {c.required_missing.length > 3 ? "…" : ""}
                    </span>
                  )}
                </td>
                {showCompanies && (
                  <td className="bulk-skills-cell">
                    {c.companies_matched.length > 0 && (
                      <span className="bulk-skill-chip bulk-skill-match" title={c.companies_matched.join(", ")}>
                        {c.companies_matched.join(", ")}
                      </span>
                    )}
                    {c.companies_missing.length > 0 && (
                      <span className="bulk-skill-chip bulk-skill-missing" title={c.companies_missing.join(", ")}>
                        no match
                      </span>
                    )}
                  </td>
                )}
                <td>{c.years_experience ?? "?"} yrs</td>
                <td>
                  <button className="secondary-button" onClick={() => onViewFull(c.filename)}>
                    View full analysis
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.failed.length > 0 && (
        <div className="bulk-failed-list">
          <h4>Could not process</h4>
          <ul>
            {result.failed.map((f) => (
              <li key={f.filename}>
                <strong>{f.filename}</strong>: {f.error}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
