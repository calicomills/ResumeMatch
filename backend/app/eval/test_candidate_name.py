"""Regression coverage for a real bug: the background-check summary referred to the candidate by
their GitHub username ("Calicomills, a Python developer... His GitHub...") because it had no
other identifier. This is the deterministic name guess that fixes it.
"""

from app.parsing.candidate_name import guess_candidate_name


def test_extracts_name_from_first_line():
    text = "Jishnu C K\nSenior Backend Engineer\nEmail: jishnuck26@gmail.com\n"
    assert guess_candidate_name(text) == "Jishnu C K"


def test_skips_a_literal_resume_header_line():
    text = "Resume\nJane Doe\nSoftware Engineer\n"
    assert guess_candidate_name(text) == "Jane Doe"


def test_gives_up_when_first_line_has_an_email():
    text = "jane@example.com\nJane Doe\n"
    assert guess_candidate_name(text) is None


def test_gives_up_when_first_line_has_a_digit():
    text = "+1 555-123-4567\nJane Doe\n"
    assert guess_candidate_name(text) is None


def test_gives_up_when_first_line_is_not_title_case():
    text = "senior backend engineer resume\nJane Doe\n"
    assert guess_candidate_name(text) is None


def test_gives_up_when_first_line_is_too_long():
    text = "This Is Definitely Not A Name It Is Way Too Long\n"
    assert guess_candidate_name(text) is None


def test_empty_text_returns_none():
    assert guess_candidate_name("") is None
    assert guess_candidate_name("\n\n\n") is None
