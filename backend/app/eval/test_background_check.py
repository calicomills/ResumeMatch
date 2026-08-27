import pytest

from app.background_check.github_check import GithubProfile
from app.background_check.summarize import _fallback_summary, generate_background_summary
from app.eval.fakes import FakeOllamaClient


def test_fallback_summary_covers_found_and_missing_github():
    found = GithubProfile(username="janedoe", found=True, public_repos=10, followers=3, top_languages=["Python"])
    missing = GithubProfile(username="ghost", found=False, error="GitHub user not found")
    summary = _fallback_summary([found, missing], [], candidate_name=None)
    assert "@janedoe" in summary
    assert "10 public repos" in summary
    assert "not found" in summary


def test_fallback_summary_uses_candidate_name_not_username():
    # Regression: the summary used to read "Calicomills, a Python developer..." — the GitHub
    # username standing in for the candidate's actual name.
    found = GithubProfile(username="calicomills", found=True, public_repos=10, followers=3)
    summary = _fallback_summary([found], [], candidate_name="Jishnu C K")
    assert summary.startswith("Jishnu C K's GitHub (@calicomills):")
    assert "Calicomills," not in summary


def test_fallback_summary_without_name_says_the_candidate():
    found = GithubProfile(username="calicomills", found=True, public_repos=10)
    summary = _fallback_summary([found], [], candidate_name=None)
    assert summary.startswith("The candidate's GitHub (@calicomills):")


def test_fallback_summary_with_no_links():
    assert "No links found" in _fallback_summary([], [], candidate_name=None)


@pytest.mark.asyncio
async def test_generate_background_summary_uses_llm_text_when_valid():
    fake = FakeOllamaClient(generate_text="Active GitHub profile, 10 repos, recently updated.")
    profile = GithubProfile(username="janedoe", found=True, public_repos=10)
    summary = await generate_background_summary(fake, [profile], [])
    assert summary == "Active GitHub profile, 10 repos, recently updated."


@pytest.mark.asyncio
async def test_generate_background_summary_falls_back_on_ollama_failure():
    fake = FakeOllamaClient(raise_on_generate=True)
    profile = GithubProfile(username="janedoe", found=True, public_repos=10, top_languages=["Python"])
    summary = await generate_background_summary(fake, [profile], [], candidate_name="Jane Doe")
    assert "Jane Doe" in summary  # templated fallback, not an exception, and uses the real name


@pytest.mark.asyncio
async def test_generate_background_summary_with_no_links_skips_llm_call():
    fake = FakeOllamaClient(raise_on_generate=True)  # would raise if called
    summary = await generate_background_summary(fake, [], [])
    assert "No GitHub or personal site links" in summary


@pytest.mark.asyncio
async def test_generate_background_summary_passes_candidate_name_to_the_model():
    fake = FakeOllamaClient(generate_text="placeholder")
    profile = GithubProfile(username="calicomills", found=True, public_repos=10)
    captured = {}

    async def capturing_generate(prompt, system=None):
        captured["prompt"] = prompt
        return "Jishnu C K's GitHub is active with 10 public repos."

    fake.generate = capturing_generate
    summary = await generate_background_summary(fake, [profile], [], candidate_name="Jishnu C K")
    assert '"candidate_name": "Jishnu C K"' in captured["prompt"]
    assert summary == "Jishnu C K's GitHub is active with 10 public repos."
