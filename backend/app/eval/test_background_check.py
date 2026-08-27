import pytest

from app.background_check.github_check import GithubProfile
from app.background_check.summarize import _fallback_summary, generate_background_summary
from app.eval.fakes import FakeOllamaClient


def test_fallback_summary_covers_found_and_missing_github():
    found = GithubProfile(username="janedoe", found=True, public_repos=10, followers=3, top_languages=["Python"])
    missing = GithubProfile(username="ghost", found=False, error="GitHub user not found")
    summary = _fallback_summary([found, missing], [])
    assert "janedoe" in summary
    assert "10 public repos" in summary
    assert "not found" in summary


def test_fallback_summary_with_no_links():
    assert "No links found" in _fallback_summary([], [])


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
    summary = await generate_background_summary(fake, [profile], [])
    assert "janedoe" in summary  # templated fallback, not an exception


@pytest.mark.asyncio
async def test_generate_background_summary_with_no_links_skips_llm_call():
    fake = FakeOllamaClient(raise_on_generate=True)  # would raise if called
    summary = await generate_background_summary(fake, [], [])
    assert "No GitHub or personal site links" in summary
