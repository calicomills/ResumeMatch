"""Full-pipeline integration test: real FastAPI app, real parsing/scoring code, but the Ollama
client and outbound background-check calls are swapped for deterministic fakes so the suite is
hermetic (no network, no local model required to run `pytest`).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.routers.analyze as analyze_module
import app.routers.health as health_module
from app.background_check.github_check import GithubProfile
from app.background_check.website_check import WebsiteCheck
from app.eval.fakes import FakeOllamaClient
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client(monkeypatch):
    fake = FakeOllamaClient(
        jd_response={
            "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            "nice_to_have_skills": ["Kubernetes", "AWS"],
            "min_years_experience": 3,
            "education": "Bachelor's in CS",
        },
        resume_response={
            "skills": ["Python", "Django", "PostgreSQL", "Docker", "Git"],
            "years_experience": 4,
            "education": "B.S. in Computer Science",
            "highlights": ["Built REST APIs", "Containerized services"],
        },
        questions_response=[
            "Have you used FastAPI specifically, or mainly Django?",
            "Any hands-on AWS experience you'd want to highlight?",
        ],
    )

    async def fake_github(username: str) -> GithubProfile:
        return GithubProfile(
            username=username, found=True, public_repos=12, followers=5, top_languages=["Python"]
        )

    async def fake_website(url: str) -> WebsiteCheck:
        return WebsiteCheck(url=url, reachable=True, status_code=200, title="Jane Doe")

    monkeypatch.setattr(analyze_module, "OllamaClient", lambda: fake)
    monkeypatch.setattr(analyze_module, "check_github", fake_github)
    monkeypatch.setattr(analyze_module, "check_website", fake_website)
    monkeypatch.setattr(health_module, "OllamaClient", lambda: fake)

    return TestClient(app)


def test_analyze_end_to_end_with_pasted_text(client):
    jd_text = (FIXTURES / "sample_jd.txt").read_text()
    resume_text = (FIXTURES / "sample_resume.txt").read_text()

    resp = client.post("/api/analyze", data={"jd_text": jd_text, "resume_text": resume_text})
    assert resp.status_code == 200
    body = resp.json()

    assert 0 <= body["match"]["score"] <= 100
    assert "python" in body["match"]["required_matched"]
    assert "fastapi" in body["match"]["required_missing"]  # resume says Django, not FastAPI
    assert body["interview_questions"], "gaps exist (FastAPI/Kubernetes/AWS), so questions must be generated"
    assert body["links"]["github"], "sample resume includes a github.com link"
    assert body["background_check"]["github_profiles"][0]["public_repos"] == 12
    assert body["background_check"]["summary"]


def test_analyze_requires_jd_or_resume_text(client):
    resp = client.post("/api/analyze", data={"resume_text": "some resume"})
    assert resp.status_code == 400


def test_analyze_rejects_unsupported_file_type(client):
    resp = client.post(
        "/api/analyze",
        data={"resume_text": "some resume"},
        files={"jd_file": ("jd.exe", b"not a real jd", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_health_endpoint_reports_ollama_status(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ollama_reachable"] is True
    assert body["model_loaded"] is True
