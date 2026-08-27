"""Regression coverage for a real bug: the LLM extracted 27 years of experience from a resume
whose own summary says "7.5+ years", because date arithmetic was left to a 1.5B model. These
tests exercise the deterministic replacement directly against date-range text.
"""

from datetime import date

from app.parsing.experience import estimate_years_experience

TODAY = date(2026, 8, 27)


def test_single_range_with_months():
    text = "Experience\nSoftware Engineer, Acme (Jan 2020 - Mar 2022)\n"
    assert estimate_years_experience(text, today=TODAY) == 2


def test_present_uses_today():
    text = "Experience\nEngineer, Acme (Sep 2018 - Present)\n"
    # Sep 2018 -> Aug 2026 is 95 months = ~7.9 years, rounds to 8
    assert estimate_years_experience(text, today=TODAY) == 8


def test_multiple_sequential_roles_sum_correctly():
    text = """Experience
    Senior Engineer, Acme (May 2023 - Present)
    R&D Engineer, Beta (Feb 2021 - May 2023)
    Software Engineer, Gamma (Sep 2018 - Feb 2021)
    """
    # Sep 2018 -> Aug 2026, contiguous, no gaps: ~95 months -> 8 years
    assert estimate_years_experience(text, today=TODAY) == 8


def test_education_section_is_not_counted_as_experience():
    # Reproduces the real bug scenario: an Experience section followed by an Education section
    # with its own date range. The education years must not be added to work experience.
    text = """Experience
    Senior Engineer, Acme (May 2023 - Present)
    R&D Engineer, Beta (Feb 2021 - May 2023)
    Software Engineer, Gamma (Sep 2018 - Feb 2021)

    Education & Certifications
    B.Tech in Electrical and Electronics Engineering
    National Institute of Technology (2014 - 2018)
    """
    assert estimate_years_experience(text, today=TODAY) == 8


def test_overlapping_concurrent_roles_are_not_double_counted():
    text = """Experience
    Consultant, SideCo (Jan 2021 - Dec 2022)
    Engineer, MainCo (Jan 2020 - Jan 2022)
    """
    # union of [2020-01, 2022-01] and [2021-01, 2022-12] = 2020-01 to 2022-12 = 36 months = 3 yrs
    assert estimate_years_experience(text, today=TODAY) == 3


def test_year_only_ranges_without_month_names():
    text = "Experience\nSoftware Engineer, Acme Corp (2019 - 2023)\n"
    assert estimate_years_experience(text, today=TODAY) == 5


def test_no_parseable_dates_returns_none():
    assert estimate_years_experience("Experience\nDid a lot of great work.\n") is None


def test_no_experience_section_at_all_returns_none():
    assert estimate_years_experience("Just some text with no headings or dates.") is None
