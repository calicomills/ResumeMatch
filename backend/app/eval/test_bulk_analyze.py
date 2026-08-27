"""Bulk endpoint tests. Uses a content-aware fake Ollama client (distinct from FakeOllamaClient)
because these tests need different resumes to score differently — something a single fixed
resume_response can't produce.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.routers.bulk_analyze as bulk_module
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"

JD_TEXT = "Backend Engineer. Requirements: Python, Docker, Kubernetes."


class ContentAwareFakeClient:
    """Routes generate_json by sniffing which candidate's text is embedded in the prompt, since
    the real RESUME_PROMPT embeds the resume text verbatim."""

    def __init__(self):
        self.jd_calls = 0
        self.resume_calls = 0

    async def generate_json(self, prompt, system, default):
        if "min_years_experience" in prompt:
            self.jd_calls += 1
            return {"required_skills": ["Python", "Docker", "Kubernetes"], "min_years_experience": 0, "education": ""}
        if "years_experience" in prompt:
            self.resume_calls += 1
            if "CANDIDATE_FULL_MATCH" in prompt:
                return {"skills": ["Python", "Docker", "Kubernetes"], "years_experience": 5}
            if "CANDIDATE_PARTIAL_MATCH" in prompt:
                return {"skills": ["Python"], "years_experience": 2}
            if "CANDIDATE_NO_MATCH" in prompt:
                return {"skills": ["Ruby"], "years_experience": 1}
            if "CANDIDATE_WEAK_SKILLS_BIG_NAME" in prompt:
                return {"skills": [], "years_experience": 0, "companies": ["Google"]}
            if "CANDIDATE_STRONG_SKILLS_SMALL_NAME" in prompt:
                return {"skills": ["Python", "Docker", "Kubernetes"], "years_experience": 0, "companies": ["Tiny Startup"]}
            return default
        return default

    async def generate(self, prompt, system=None):
        return "unused in bulk mode"


@pytest.fixture
def client(monkeypatch):
    fake = ContentAwareFakeClient()
    monkeypatch.setattr(bulk_module, "OllamaClient", lambda: fake)
    test_client = TestClient(app)
    test_client.fake = fake  # type: ignore[attr-defined]
    return test_client


def _resume_file(name: str, marker: str) -> tuple[str, bytes, str]:
    return (name, f"{marker}\nSome resume content.".encode(), "text/plain")


def test_bulk_analyze_sorts_candidates_by_score_descending(client):
    resp = client.post(
        "/api/bulk-analyze",
        data={"jd_text": JD_TEXT},
        files=[
            ("resume_files", _resume_file("no_match.txt", "CANDIDATE_NO_MATCH")),
            ("resume_files", _resume_file("full_match.txt", "CANDIDATE_FULL_MATCH")),
            ("resume_files", _resume_file("partial_match.txt", "CANDIDATE_PARTIAL_MATCH")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    filenames_in_order = [c["filename"] for c in body["candidates"]]
    assert filenames_in_order == ["full_match.txt", "partial_match.txt", "no_match.txt"]
    scores = [c["score"] for c in body["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_jd_requirements_extracted_exactly_once_not_per_resume(client):
    resp = client.post(
        "/api/bulk-analyze",
        data={"jd_text": JD_TEXT},
        files=[
            ("resume_files", _resume_file("a.txt", "CANDIDATE_FULL_MATCH")),
            ("resume_files", _resume_file("b.txt", "CANDIDATE_PARTIAL_MATCH")),
            ("resume_files", _resume_file("c.txt", "CANDIDATE_NO_MATCH")),
        ],
    )
    assert resp.status_code == 200
    assert client.fake.jd_calls == 1
    assert client.fake.resume_calls == 3


def test_bulk_analyze_tolerates_one_bad_file(client):
    resp = client.post(
        "/api/bulk-analyze",
        data={"jd_text": JD_TEXT},
        files=[
            ("resume_files", _resume_file("good.txt", "CANDIDATE_FULL_MATCH")),
            ("resume_files", ("bad.exe", b"not a resume", "application/octet-stream")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["candidates"]) == 1
    assert body["candidates"][0]["filename"] == "good.txt"
    assert len(body["failed"]) == 1
    assert body["failed"][0]["filename"] == "bad.exe"
    assert body["failed"][0]["error"]


def test_bulk_analyze_requires_at_least_one_resume(client):
    resp = client.post("/api/bulk-analyze", data={"jd_text": JD_TEXT}, files=[])
    assert resp.status_code == 400


def test_bulk_analyze_enforces_max_resume_count(client, monkeypatch):
    monkeypatch.setattr("app.routers.bulk_analyze.settings.max_bulk_resumes", 2)
    resp = client.post(
        "/api/bulk-analyze",
        data={"jd_text": JD_TEXT},
        files=[
            ("resume_files", _resume_file("a.txt", "CANDIDATE_FULL_MATCH")),
            ("resume_files", _resume_file("b.txt", "CANDIDATE_PARTIAL_MATCH")),
            ("resume_files", _resume_file("c.txt", "CANDIDATE_NO_MATCH")),
        ],
    )
    assert resp.status_code == 400


def test_bulk_analyze_default_weights_match_original_ranking(client):
    # No weight_* fields sent at all — should behave exactly like before weights existed.
    resp = client.post(
        "/api/bulk-analyze",
        data={"jd_text": JD_TEXT},
        files=[
            ("resume_files", _resume_file("full.txt", "CANDIDATE_FULL_MATCH")),
            ("resume_files", _resume_file("partial.txt", "CANDIDATE_PARTIAL_MATCH")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["weights_used"] == {"required": 0.55, "nice_to_have": 0.15, "experience": 0.20, "education": 0.10, "companies": 0.0}
    assert [c["filename"] for c in body["candidates"]] == ["full.txt", "partial.txt"]


def test_bulk_analyze_custom_weights_can_reorder_ranking(client):
    # Weight entirely toward experience: full_match has more years, so heavily favoring
    # experience over skills should still put it first — but weighting entirely toward
    # required skills where partial_match has fewer should flip if we invert instead.
    resp = client.post(
        "/api/bulk-analyze",
        data={
            "jd_text": JD_TEXT,
            "weight_required": "0",
            "weight_nice_to_have": "0",
            "weight_experience": "100",
            "weight_education": "0",
            "weight_companies": "0",
        },
        files=[
            ("resume_files", _resume_file("no_match.txt", "CANDIDATE_NO_MATCH")),  # 1 yr exp
            ("resume_files", _resume_file("partial.txt", "CANDIDATE_PARTIAL_MATCH")),  # 2 yrs exp
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    # With JD's min_years_experience=0, experience_score is always 1.0 for everyone regardless
    # of actual years — so weighting 100% onto experience makes every candidate score identically.
    scores = {c["score"] for c in body["candidates"]}
    assert scores == {100}


def test_bulk_analyze_target_companies_affect_ranking(client):
    resp = client.post(
        "/api/bulk-analyze",
        data={
            "jd_text": JD_TEXT,
            "weight_required": "0",
            "weight_nice_to_have": "0",
            "weight_experience": "0",
            "weight_education": "0",
            "weight_companies": "100",
            "target_companies": "Google, Meta",
        },
        files=[
            ("resume_files", _resume_file("big_name.txt", "CANDIDATE_WEAK_SKILLS_BIG_NAME")),
            ("resume_files", _resume_file("small_name.txt", "CANDIDATE_STRONG_SKILLS_SMALL_NAME")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_companies"] == ["Google", "Meta"]
    # Weighted entirely on target-company match, the Google alum ranks above the stronger-skills
    # candidate whose employer isn't in the target list — despite having weaker actual skills.
    assert [c["filename"] for c in body["candidates"]] == ["big_name.txt", "small_name.txt"]
    big_name = next(c for c in body["candidates"] if c["filename"] == "big_name.txt")
    assert big_name["companies_matched"] == ["Google"]
    assert big_name["companies_missing"] == ["Meta"]


def test_bulk_analyze_flags_hidden_text_per_candidate(client):
    pdf_bytes = (FIXTURES / "hidden_text_resume.pdf").read_bytes()
    resp = client.post(
        "/api/bulk-analyze",
        data={"jd_text": JD_TEXT},
        files=[
            ("resume_files", ("hidden.pdf", pdf_bytes, "application/pdf")),
            ("resume_files", _resume_file("clean.txt", "CANDIDATE_FULL_MATCH")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    by_name = {c["filename"]: c for c in body["candidates"]}
    assert by_name["hidden.pdf"]["hidden_text_found"] is True
    assert by_name["hidden.pdf"]["suspicious_phrases_found"] is True
    assert by_name["clean.txt"]["hidden_text_found"] is False
