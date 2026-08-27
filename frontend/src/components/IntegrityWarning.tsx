import type { IntegrityCheck } from "../api";

const REASON_LABELS: Record<string, string> = {
  white_on_white: "white text on a white background",
  tiny_font: "near-invisible font size",
  off_page: "positioned off the visible page",
};

export function IntegrityWarning({ integrity }: { integrity: IntegrityCheck }) {
  if (!integrity.checked) return null;

  const hasIssues = integrity.hidden_text_found || integrity.suspicious_phrases.length > 0;

  if (!hasIssues) {
    return (
      <div className="integrity-note integrity-ok">
        ✓ No hidden text or LLM-manipulation attempts detected in this PDF.
      </div>
    );
  }

  return (
    <div className="integrity-note integrity-warn">
      <strong>⚠ This resume contains content hidden from a human reader.</strong>
      <p>
        Some resumes hide instructions aimed at automated screeners — the text below was excluded
        from scoring, but you should know it was there.
      </p>

      {integrity.hidden_text_spans.length > 0 && (
        <div className="integrity-section">
          <h4>Hidden text found</h4>
          <ul>
            {integrity.hidden_text_spans.map((span, i) => (
              <li key={i}>
                <span className="integrity-reason">{REASON_LABELS[span.reason] ?? span.reason} (page {span.page}):</span>
                <blockquote>"{span.text}"</blockquote>
              </li>
            ))}
          </ul>
        </div>
      )}

      {integrity.suspicious_phrases.length > 0 && (
        <div className="integrity-section">
          <h4>Manipulative phrasing detected</h4>
          <ul>
            {integrity.suspicious_phrases.map((phrase, i) => (
              <li key={i}>
                <blockquote>"{phrase}"</blockquote>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
