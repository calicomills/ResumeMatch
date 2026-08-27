"""Deterministic best-effort guess at the candidate's name, read off the resume itself.

Resumes overwhelmingly put the candidate's name as the very first line, ahead of a title, contact
info, or anything else. We use that convention rather than asking the LLM to infer identity — and
if the first line doesn't look like a plausible name, we give up (return None) rather than risk
mislabeling a section heading or job title as someone's name.
"""

from __future__ import annotations

_NON_NAME_FIRST_LINES = {"resume", "cv", "curriculum vitae", "curriculum vitae (cv)"}
_MAX_NAME_WORDS = 5


def guess_candidate_name(resume_text: str) -> str | None:
    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        lower = stripped.lower()
        if lower in _NON_NAME_FIRST_LINES:
            continue  # skip a literal "Resume" / "CV" header line, keep looking

        if "@" in stripped or any(ch.isdigit() for ch in stripped):
            return None  # looks like contact info or a heading with a date, not a name
        words = stripped.split()
        if not (1 <= len(words) <= _MAX_NAME_WORDS):
            return None  # too long/short to plausibly be just a name
        if not all(w[0].isalpha() and w[0].isupper() for w in words):
            return None  # doesn't read as Title Case the way names typically do

        return stripped

    return None
