"""Deterministic JD/resume match scoring.

The match percentage is intentionally never asked of the LLM: a small model asked "give this
resume a match score" produces an inconsistent number that changes between runs on identical
input. This is plain arithmetic over the structured fields the LLM already extracted, so the
same JD/resume pair always gets the same score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.skills.extract import JDRequirements, ResumeProfile
from app.skills.taxonomy import skills_equivalent

# Weights sum to 1.0. Required skills dominate; education is the softest signal.
WEIGHT_REQUIRED = 0.55
WEIGHT_NICE_TO_HAVE = 0.15
WEIGHT_EXPERIENCE = 0.20
WEIGHT_EDUCATION = 0.10

EDUCATION_FUZZY_THRESHOLD = 60


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


def compute_match(jd: JDRequirements, resume: ResumeProfile) -> MatchResult:
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

    weighted = (
        required_score * WEIGHT_REQUIRED
        + nice_score * WEIGHT_NICE_TO_HAVE
        + experience_score * WEIGHT_EXPERIENCE
        + education_score * WEIGHT_EDUCATION
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
        gaps=gaps,
        breakdown={
            "required_skills": round(required_score, 3),
            "nice_to_have_skills": round(nice_score, 3),
            "experience": round(experience_score, 3),
            "education": round(education_score, 3),
        },
    )
