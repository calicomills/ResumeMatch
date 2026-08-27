"""Deterministic JD/resume match scoring.

The match percentage is intentionally never asked of the LLM: a small model asked "give this
resume a match score" produces an inconsistent number that changes between runs on identical
input. This is plain arithmetic over the structured fields the LLM already extracted, so the
same JD/resume pair always gets the same score.

Weights are recruiter-adjustable (see MatchWeights) rather than fixed, but the defaults reproduce
the original fixed ratios exactly, so nothing changes for a caller that doesn't pass any.

Company matching follows the same rule as skills: the recruiter names companies they value (a
target list), and matching is plain overlap against what's on the resume — never an LLM judgment
call about which employers are "impressive." That's a subjective, bias-prone question this app
doesn't ask a model to answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.skills.extract import JDRequirements, ResumeProfile
from app.skills.taxonomy import skills_equivalent

EDUCATION_FUZZY_THRESHOLD = 60
COMPANY_FUZZY_THRESHOLD = 80


@dataclass
class MatchWeights:
    """Relative importance of each scoring dimension. Values are relative, not required to sum
    to anything in particular — normalized() divides by their total. Defaults reproduce the
    app's original fixed weighting."""

    required: float = 55
    nice_to_have: float = 15
    experience: float = 20
    education: float = 10
    companies: float = 0  # 0 by default: irrelevant unless the recruiter names target companies

    def normalized(self) -> MatchWeights:
        total = self.required + self.nice_to_have + self.experience + self.education + self.companies
        if total <= 0:
            return MatchWeights().normalized()
        return MatchWeights(
            required=self.required / total,
            nice_to_have=self.nice_to_have / total,
            experience=self.experience / total,
            education=self.education / total,
            companies=self.companies / total,
        )


@dataclass
class Gap:
    kind: str  # "required_skill" | "experience" | "nice_to_have_skill" | "education"
    label: str


@dataclass
class MatchResult:
    score: int
    required_matched: list[str] = field(default_factory=list)
    required_missing: list[str] = field(default_factory=list)
    nice_to_have_matched: list[str] = field(default_factory=list)
    nice_to_have_missing: list[str] = field(default_factory=list)
    experience_ok: bool = True
    experience_detail: str = ""
    education_ok: bool = True
    companies_matched: list[str] = field(default_factory=list)
    companies_missing: list[str] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    breakdown: dict[str, float] = field(default_factory=dict)


def _split_matches(required: list[str], resume_skills: list[str]) -> tuple[list[str], list[str]]:
    matched, missing = [], []
    for skill in required:
        if any(skills_equivalent(skill, rs) for rs in resume_skills):
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing


def _split_company_matches(
    target_companies: list[str], resume_companies: list[str]
) -> tuple[list[str], list[str]]:
    matched, missing = [], []
    for target in target_companies:
        if any(fuzz.WRatio(target.lower(), rc.lower()) >= COMPANY_FUZZY_THRESHOLD for rc in resume_companies):
            matched.append(target)
        else:
            missing.append(target)
    return matched, missing


def compute_match(
    jd: JDRequirements,
    resume: ResumeProfile,
    weights: MatchWeights | None = None,
    target_companies: list[str] | None = None,
) -> MatchResult:
    w = (weights or MatchWeights()).normalized()
    target_companies = target_companies or []

    required_matched, required_missing = _split_matches(jd.required_skills, resume.skills)
    nice_matched, nice_missing = _split_matches(jd.nice_to_have_skills, resume.skills)

    required_score = (len(required_matched) / len(jd.required_skills)) if jd.required_skills else 1.0
    nice_score = (len(nice_matched) / len(jd.nice_to_have_skills)) if jd.nice_to_have_skills else 1.0

    if jd.min_years_experience <= 0:
        experience_score = 1.0
        experience_ok = True
        experience_detail = "No minimum experience stated in the JD."
    else:
        experience_score = min(1.0, resume.years_experience / jd.min_years_experience)
        experience_ok = resume.years_experience >= jd.min_years_experience
        experience_detail = (
            f"{resume.years_experience} yrs on resume vs {jd.min_years_experience} yrs required"
        )

    if not jd.education:
        education_score = 1.0
        education_ok = True
    elif not resume.education:
        education_score = 0.0
        education_ok = False
    else:
        similarity = fuzz.partial_ratio(jd.education.lower(), resume.education.lower())
        education_ok = similarity >= EDUCATION_FUZZY_THRESHOLD
        education_score = 1.0 if education_ok else 0.4  # partial credit; education is soft signal

    if not target_companies:
        # No target list from the recruiter: this dimension has no signal to contribute. Scored
        # neutral (1.0) rather than penalizing every candidate equally for a criterion nobody set.
        companies_score = 1.0
        companies_matched: list[str] = []
        companies_missing: list[str] = []
    else:
        companies_matched, companies_missing = _split_company_matches(target_companies, resume.companies)
        companies_score = len(companies_matched) / len(target_companies)

    weighted = (
        required_score * w.required
        + nice_score * w.nice_to_have
        + experience_score * w.experience
        + education_score * w.education
        + companies_score * w.companies
    )
    score = round(weighted * 100)

    gaps: list[Gap] = [Gap(kind="required_skill", label=s) for s in required_missing]
    if not experience_ok:
        gaps.append(Gap(kind="experience", label=experience_detail))
    if not education_ok and jd.education:
        gaps.append(Gap(kind="education", label=f"JD wants: {jd.education}"))
    for s in nice_missing:
        gaps.append(Gap(kind="nice_to_have_skill", label=s))

    return MatchResult(
        score=score,
        required_matched=required_matched,
        required_missing=required_missing,
        nice_to_have_matched=nice_matched,
        nice_to_have_missing=nice_missing,
        experience_ok=experience_ok,
        experience_detail=experience_detail,
        education_ok=education_ok,
        companies_matched=companies_matched,
        companies_missing=companies_missing,
        gaps=gaps,
        breakdown={
            "required_skills": round(required_score, 3),
            "nice_to_have_skills": round(nice_score, 3),
            "experience": round(experience_score, 3),
            "education": round(education_score, 3),
            "companies": round(companies_score, 3),
        },
    )
