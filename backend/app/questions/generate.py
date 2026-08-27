"""Turn a (code-computed) list of gaps into interview questions a recruiter can actually ask.

The model is never asked to find the gaps — `scoring/match.py` already did that deterministically.
It is only asked to phrase one good question per gap. If it returns something malformed or the
wrong shape, we fill in a templated question rather than re-prompting: a fallback the recruiter
can still use beats a blank result or a retry loop.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.llm.ollama_client import OllamaClientProtocol
from app.scoring.match import Gap

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


def _prioritize(gaps: list[Gap]) -> list[Gap]:
    order = {"required_skill": 0, "experience": 1, "education": 2, "nice_to_have_skill": 3}
    return sorted(gaps, key=lambda g: order.get(g.kind, 9))[:MAX_QUESTIONS]


async def generate_questions(client: OllamaClientProtocol, gaps: list[Gap]) -> list[InterviewQuestion]:
    if not gaps:
        return []

    selected = _prioritize(gaps)
    gap_lines = "\n".join(f"{i+1}. [{g.kind}] {g.label}" for i, g in enumerate(selected))
    prompt = PROMPT_TEMPLATE.format(gap_lines=gap_lines, n=len(selected))

    raw = await client.generate_json(prompt, SYSTEM, default=[])

    results: list[InterviewQuestion] = []
    for i, gap in enumerate(selected):
        question_text = None
        if isinstance(raw, list) and i < len(raw):
            candidate = raw[i]
            if isinstance(candidate, str) and len(candidate.strip()) >= 10:
                question_text = candidate.strip()
            elif isinstance(candidate, dict):
                # tolerate {"question": "..."} shape too
                q = candidate.get("question")
                if isinstance(q, str) and len(q.strip()) >= 10:
                    question_text = q.strip()

        if question_text:
            results.append(InterviewQuestion(gap.kind, gap.label, question_text, source="llm"))
        else:
            results.append(InterviewQuestion(gap.kind, gap.label, _fallback(gap), source="fallback"))

    return results
