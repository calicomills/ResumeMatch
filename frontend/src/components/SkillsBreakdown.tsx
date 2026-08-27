import type { JDRequirements, MatchResult, ResumeProfile } from "../api";

interface Props {
  match: MatchResult;
  jd: JDRequirements;
  resume: ResumeProfile;
}

export function SkillsBreakdown({ match, jd, resume }: Props) {
  return (
    <div className="skills-breakdown">
      <SkillRow title="Required skills" matched={match.required_matched} missing={match.required_missing} />
      <SkillRow
        title="Nice-to-have skills"
        matched={match.nice_to_have_matched}
        missing={match.nice_to_have_missing}
      />
      <div className="fact-row">
        <FactPill
          ok={match.experience_ok}
          label={match.experience_detail || `${resume.years_experience} yrs on resume`}
        />
        <FactPill
          ok={match.education_ok}
          label={
            jd.education
              ? `Education: ${resume.education || "not stated"} (JD wants ${jd.education})`
              : `Education: ${resume.education || "not stated"}`
          }
        />
      </div>
    </div>
  );
}

function SkillRow({ title, matched, missing }: { title: string; matched: string[]; missing: string[] }) {
  if (matched.length === 0 && missing.length === 0) return null;
  return (
    <div className="skill-row">
      <h3>{title}</h3>
      <div className="chip-row">
        {matched.map((s) => (
          <span key={s} className="chip chip-match">
            {s}
          </span>
        ))}
        {missing.map((s) => (
          <span key={s} className="chip chip-missing">
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}

function FactPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`fact-pill ${ok ? "fact-ok" : "fact-warn"}`}>
      {ok ? "✓" : "!"} {label}
    </span>
  );
}
