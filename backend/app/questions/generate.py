"""Turn a (code-computed) list of gaps into interview questions a recruiter can actually ask.

The model is never asked to find the gaps — `scoring/match.py` already did that deterministically.
It is only asked to phrase one good question per gap. If it returns something malformed or the
wrong shape, we fill in a templated question rather than re-prompting: a fallback the recruiter
can still use beats a blank result or a retry loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.llm.ollama_client import OllamaClientProtocol
from app.scoring.match import Gap
from app.skills.taxonomy import is_technical_skill

MAX_QUESTIONS = 6

SYSTEM = (
    "You write sharp, specific interview questions for a recruiter to ask a candidate. "
    "Reply with ONLY a JSON array of strings, one question per gap, in the same order given. "
    "No prose, no markdown fences."
)

PROMPT_TEMPLATE = """The recruiter is evaluating a candidate against a job description. Here are
gaps between what the job requires and what the resume shows, in priority order:

{gap_lines}

Write exactly {n} interview questions, one per gap in order, that help the recruiter probe each
gap directly. Be specific to the gap, not generic. Reply with ONLY a JSON array of {n} strings.
"""

# Plain English, not a [bracket_tag] — a small model asked to write around "[nice_to_have_skill]"
# will sometimes just copy that literal token into its answer ("What experience do you have with
# [nice_to_have_skill] hadoop?") rather than treat it as metadata. _is_usable_question below is
# the belt-and-suspenders check: even with this wording, a leak is caught, not trusted away.
_GAP_KIND_DESCRIPTIONS = {
    "required_skill": "missing required skill",
    "nice_to_have_skill": "missing nice-to-have skill",
    "experience": "experience gap",
    "education": "education gap",
}

# Catches the failure mode above regardless of prompt wording — any bracketed internal gap-kind
# token leaking into the model's output means the answer isn't trustworthy prose, so it's treated
# the same as a too-short or missing response: fall back to the template, don't try to clean it up.
_LEAKED_TAG_RE = re.compile(
    r"\[\s*(required_skill|nice_to_have_skill|experience|education)\s*\]", re.IGNORECASE
)


def _is_usable_question(text: str) -> bool:
    return len(text) >= 10 and not _LEAKED_TAG_RE.search(text)


_FALLBACK_TEMPLATES = {
    "required_skill": "Can you walk me through a project where you used {label}? What was your specific role, and how comfortable are you with it today?",
    "nice_to_have_skill": "The role lists {label} as a nice-to-have — do you have any exposure to it?",
    "experience": "This role expects more experience than the resume shows ({label}). What relevant experience might not be fully reflected there?",
    "education": "The role's education expectation is: {label}. Can you tell me about your background here, including any equivalent experience?",
}


@dataclass
class InterviewQuestion:
    gap_kind: str
    gap_label: str
    question: str
    source: str  # "llm" | "fallback"


def _fallback(gap: Gap) -> str:
    template = _FALLBACK_TEMPLATES.get(gap.kind, "Can you tell me more about {label}?")
    return template.format(label=gap.label)


_SKILL_GAP_KINDS = {"required_skill", "nice_to_have_skill"}
_KIND_ORDER = {"required_skill": 0, "nice_to_have_skill": 1, "experience": 2, "education": 3}


def _priority_key(gap: Gap) -> tuple[int, int]:
    # Technical skill gaps first (tier 0), everything else after (tier 1) — a recruiter's
    # question budget is better spent probing a missing technology than a missing business
    # skill or a soft experience/education gap. Within each tier, the original kind ordering.
    is_technical_gap = gap.kind in _SKILL_GAP_KINDS and is_technical_skill(gap.label)
    tier = 0 if is_technical_gap else 1
    return (tier, _KIND_ORDER.get(gap.kind, 9))


def _prioritize(gaps: list[Gap]) -> list[Gap]:
    return sorted(gaps, key=_priority_key)[:MAX_QUESTIONS]


async def generate_questions(client: OllamaClientProtocol, gaps: list[Gap]) -> list[InterviewQuestion]:
    if not gaps:
        return []

    selected = _prioritize(gaps)
    gap_lines = "\n".join(
        f"{i+1}. {_GAP_KIND_DESCRIPTIONS.get(g.kind, g.kind)}: {g.label}" for i, g in enumerate(selected)
    )
    prompt = PROMPT_TEMPLATE.format(gap_lines=gap_lines, n=len(selected))

    raw = await client.generate_json(prompt, SYSTEM, default=[])

    results: list[InterviewQuestion] = []
    for i, gap in enumerate(selected):
        question_text = None
        if isinstance(raw, list) and i < len(raw):
            candidate = raw[i]
            if isinstance(candidate, str) and _is_usable_question(candidate.strip()):
                question_text = candidate.strip()
            elif isinstance(candidate, dict):
                # tolerate {"question": "..."} shape too
                q = candidate.get("question")
                if isinstance(q, str) and _is_usable_question(q.strip()):
                    question_text = q.strip()

        if question_text:
            results.append(InterviewQuestion(gap.kind, gap.label, question_text, source="llm"))
        else:
            results.append(InterviewQuestion(gap.kind, gap.label, _fallback(gap), source="fallback"))

    return results
