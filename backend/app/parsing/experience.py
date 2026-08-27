"""Deterministic total-years-of-experience estimate from resume date ranges.

This exists because asking the LLM to do the arithmetic ("estimate years_experience from work
history dates") is exactly the failure mode the coachLLM writeup warns about: a small model asked
to reason over several date ranges in unstructured text produces an inconsistent, sometimes wildly
wrong number (observed: 27 years extracted from a resume whose own summary says "7.5+ years").
Date-range math is something code does reliably; the LLM's answer is now only a fallback for
resumes whose experience section doesn't parse (see skills/extract.py).
"""

from __future__ import annotations

import re
from datetime import date

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Only look inside the resume's experience section — otherwise an education date range
# ("2014 - 2018") or a projects section would get counted as employment.
_SECTION_START = [r"experience", r"work experience", r"professional experience", r"employment history", r"employment"]
_SECTION_END = [
    r"education(?:\s*&\s*certifications)?", r"education", r"technical skills", r"skills",
    r"certifications", r"projects", r"publications", r"awards", r"references", r"summary",
]

_RANGE_RE = re.compile(
    r"(?P<smonth>[A-Za-z]{3,9})?\.?\s*(?P<syear>(?:19|20)\d{2})"
    r"\s*(?:[-–—]|to)\s*"
    r"(?:(?P<emonth>[A-Za-z]{3,9})?\.?\s*(?P<eyear>(?:19|20)\d{2})"
    r"|(?P<present>present|current|now|ongoing))",
    re.IGNORECASE,
)

MAX_PLAUSIBLE_YEARS = 55


def _month_num(name: str | None, default: int) -> int:
    if not name:
        return default
    return _MONTHS.get(name.strip(".").lower()[:3], default)


def _experience_section(text: str) -> str:
    lines = text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip().lower().rstrip(":")
        if any(re.fullmatch(p, stripped) for p in _SECTION_START):
            start_idx = i + 1
            break
    if start_idx is None:
        return text  # no clear heading — fall back to scanning the whole document

    end_idx = len(lines)
    for j in range(start_idx, len(lines)):
        stripped = lines[j].strip().lower().rstrip(":")
        if any(re.fullmatch(p, stripped) for p in _SECTION_END):
            end_idx = j
            break

    return "\n".join(lines[start_idx:end_idx])


def _merge_months(intervals: list[tuple[int, int]]) -> int:
    """Union overlapping/concurrent-role date ranges so they aren't double-counted, then
    return total months covered."""
    if not intervals:
        return 0
    intervals.sort()
    total = 0
    cur_start, cur_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    total += cur_end - cur_start
    return total


def estimate_years_experience(text: str, today: date | None = None) -> int | None:
    """Returns a whole-number years estimate, or None if no parseable date range was found
    (caller should fall back to the LLM's guess in that case)."""
    today = today or date.today()
    section = _experience_section(text)

    intervals: list[tuple[int, int]] = []
    for match in _RANGE_RE.finditer(section):
        start_year = int(match.group("syear"))
        start_month = _month_num(match.group("smonth"), default=1)
        start_idx = start_year * 12 + start_month

        if match.group("present"):
            end_idx = today.year * 12 + today.month
        else:
            end_year = int(match.group("eyear"))
            end_month = _month_num(match.group("emonth"), default=12)
            end_idx = end_year * 12 + end_month

        if end_idx < start_idx:
            continue  # malformed / not actually a range (e.g. mis-parsed unrelated numbers)
        intervals.append((start_idx, end_idx))

    if not intervals:
        return None

    total_months = _merge_months(intervals)
    years = round(total_months / 12)
    return max(0, min(MAX_PLAUSIBLE_YEARS, years))
