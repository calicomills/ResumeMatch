"""Unit tests for the pure regex/parsing helpers in website_check.py, without hitting the network.
The actual HTTP fetch is exercised in the docker-compose smoke test instead.
"""

from app.background_check.website_check import _clean, _DESC_RE, _TITLE_RE


def test_title_regex_extracts_title():
    html = "<html><head><title>Jane Doe — Software Engineer</title></head><body></body></html>"
    match = _TITLE_RE.search(html)
    assert match and match.group(1) == "Jane Doe — Software Engineer"


def test_description_regex_extracts_meta_description():
    html = '<meta name="description" content="Personal site of Jane Doe.">'
    match = _DESC_RE.search(html)
    assert match and match.group(1) == "Personal site of Jane Doe."


def test_clean_collapses_whitespace_and_truncates():
    assert _clean("  hello\n\n  world  ") == "hello world"
    assert len(_clean("x" * 1000)) == 300
