"""LLM-backed structured extraction of JD requirements and resume profile.

This is the one place the model does real work: pulling fields out of text it has been given.
Per the writeup's lesson, everything downstream (matching, scoring) is deterministic code, not
another model call — the model's job here is extraction and phrasing only, never judgment.

years_experience is the one field in the resume prompt below that the LLM is still *asked* for,
but it's no longer trusted: date arithmetic over several employment ranges is exactly the kind of
task a small model gets wrong in ways that are hard to predict (observed: 27 years extracted from
a resume whose own summary says "7.5+ years"). `parsing/experience.py` computes it deterministically
from regex-parsed date ranges instead; the LLM's answer is only used as a fallback when that parse
finds nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.llm.ollama_client import OllamaClientProtocol
from app.parsing.experience import estimate_years_experience
from app.skills.taxonomy import is_generic_skill, normalize_skill

JD_SYSTEM = (
    "You extract structured hiring requirements from a job description. "
    "Reply with ONLY a JSON object matching the requested shape. No prose, no markdown fences."
)

JD_PROMPT = """Job description:
---
{text}
---

Extract the hiring requirements. Reply with ONLY this JSON shape (fill in real values):
{{"required_skills": ["skill1", "skill2"], "nice_to_have_skills": ["skill3"], "min_years_experience": 0, "education": "short string or empty"}}

Rules:
- required_skills: skills/technologies stated as required or must-have.
- nice_to_have_skills: skills mentioned as a plus, preferred, or bonus.
- min_years_experience: integer years of experience required. 0 if not stated.
- education: one short phrase (e.g. "Bachelor's in CS"), or "" if not stated.
"""

RESUME_SYSTEM = (
    "You extract structured facts from a resume. Reply with ONLY a JSON object matching the "
    "requested shape. No prose, no markdown fences."
)

RESUME_PROMPT = """Resume:
---
{text}
---

Extract the candidate's profile. Reply with ONLY this JSON shape (fill in real values):
{{"skills": ["skill1", "skill2"], "years_experience": 0, "education": "short string or empty", "highlights": ["short highlight 1", "short highlight 2"], "companies": ["employer 1", "employer 2"]}}

Rules:
- skills: technologies, tools, and competencies actually demonstrated in the resume.
- years_experience: integer total years of professional experience, estimated from work history dates.
- education: highest degree + field, one short phrase, or "" if not stated.
- highlights: up to 5 short (<15 word) notable achievements or responsibilities.
- companies: past and current employer names, as written on the resume.
"""

# Keep prompts bounded — small models degrade on very long context, and it keeps latency sane.
MAX_CHARS = 6000


@dataclass
class JDRequirements:
    required_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)
    min_years_experience: int = 0
    education: str = ""


@dataclass
class ResumeProfile:
    skills: list[str] = field(default_factory=list)
    years_experience: int = 0
    education: str = ""
    highlights: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)


# Small models sometimes emit a filler token instead of an empty list when there's nothing to
# report (e.g. nice_to_have_skills: ["none"]). Treat these as "nothing", not as a literal skill.
_SENTINEL_EMPTY_VALUES = {"none", "n/a", "na", "-", "null", "unknown", "not specified", "not stated", ""}


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = [str(v).strip() for v in value if str(v).strip()]
    return [v for v in cleaned if v.lower() not in _SENTINEL_EMPTY_VALUES][:30]


def _as_int(value: object, default: int = 0) -> int:
    try:
        return max(0, min(60, int(value)))  # sane bounds; a small model can hallucinate "50 years"
    except (TypeError, ValueError):
        return default


def _as_str(value: object, default: str = "") -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) else default


def _normalize_skills(raw_skills: list[str]) -> list[str]:
    """Normalize each skill and drop generic filler ("communication", "problem solving", ...) —
    see taxonomy.GENERIC_SKILLS. Applied here, once, so nothing downstream (scoring, gap
    computation, interview questions) ever sees them."""
    normalized = (normalize_skill(s) for s in raw_skills)
    return [s for s in normalized if not is_generic_skill(s)]


async def extract_jd_requirements(client: OllamaClientProtocol, jd_text: str) -> JDRequirements:
    default = {"required_skills": [], "nice_to_have_skills": [], "min_years_experience": 0, "education": ""}
    raw = await client.generate_json(
        JD_PROMPT.format(text=jd_text[:MAX_CHARS]), JD_SYSTEM, default
    )
    if not isinstance(raw, dict):
        raw = default

    return JDRequirements(
        required_skills=_normalize_skills(_as_str_list(raw.get("required_skills"))),
        nice_to_have_skills=_normalize_skills(_as_str_list(raw.get("nice_to_have_skills"))),
        min_years_experience=_as_int(raw.get("min_years_experience")),
        education=_as_str(raw.get("education")),
    )


async def extract_resume_profile(client: OllamaClientProtocol, resume_text: str) -> ResumeProfile:
    default = {"skills": [], "years_experience": 0, "education": "", "highlights": [], "companies": []}
    raw = await client.generate_json(
        RESUME_PROMPT.format(text=resume_text[:MAX_CHARS]), RESUME_SYSTEM, default
    )
    if not isinstance(raw, dict):
        raw = default

    deterministic_years = estimate_years_experience(resume_text)
    years_experience = deterministic_years if deterministic_years is not None else _as_int(raw.get("years_experience"))

    return ResumeProfile(
        skills=_normalize_skills(_as_str_list(raw.get("skills"))),
        years_experience=years_experience,
        education=_as_str(raw.get("education")),
        highlights=_as_str_list(raw.get("highlights"))[:5],
        companies=_as_str_list(raw.get("companies"))[:15],  # not skill-normalized: names, not skills
    )
