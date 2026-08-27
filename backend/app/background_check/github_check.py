"""Pull public GitHub facts for a username found in the resume.

Only GitHub's own public REST API is used — no scraping, no guessing. Everything returned here
is a fact GitHub itself reports; the LLM is never asked what a GitHub profile "probably" looks
like, only to phrase a summary of facts we already fetched (see summarize.py).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import httpx

from app.config import settings

GITHUB_API = "https://api.github.com"


@dataclass
class GithubProfile:
    username: str
    found: bool
    profile_url: str = ""
    name: str | None = None
    bio: str | None = None
    company: str | None = None
    public_repos: int = 0
    followers: int = 0
    account_created_at: str | None = None
    top_languages: list[str] = field(default_factory=list)
    most_recent_push: str | None = None
    notable_repos: list[dict] = field(default_factory=list)
    error: str | None = None


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ResumeMatch-App"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


async def check_github(username: str) -> GithubProfile:
    url = f"{GITHUB_API}/users/{username}"
    async with httpx.AsyncClient(timeout=8.0, headers=_headers()) as client:
        try:
            resp = await client.get(url)
        except Exception as exc:  # noqa: BLE001
            return GithubProfile(username=username, found=False, error=f"{type(exc).__name__}: {exc}")

        if resp.status_code == 404:
            return GithubProfile(username=username, found=False, error="GitHub user not found")
        if resp.status_code == 403:
            return GithubProfile(username=username, found=False, error="GitHub API rate limit hit")
        if resp.status_code != 200:
            return GithubProfile(username=username, found=False, error=f"GitHub API returned HTTP {resp.status_code}")

        data = resp.json()

        repos: list[dict] = []
        try:
            repos_resp = await client.get(
                f"{GITHUB_API}/users/{username}/repos",
                params={"sort": "pushed", "per_page": 15},
            )
            if repos_resp.status_code == 200:
                repos = repos_resp.json()
        except Exception:  # noqa: BLE001
            repos = []  # profile facts still stand even if repo listing fails

        language_counts = Counter(r["language"] for r in repos if r.get("language"))
        top_languages = [lang for lang, _ in language_counts.most_common(5)]

        most_recent_push = None
        if repos:
            pushed_dates = [r.get("pushed_at") for r in repos if r.get("pushed_at")]
            if pushed_dates:
                most_recent_push = max(pushed_dates)

        notable = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:3]
        notable_repos = [
            {
                "name": r.get("name"),
                "url": r.get("html_url"),
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language"),
                "description": r.get("description"),
            }
            for r in notable
        ]

        return GithubProfile(
            username=username,
            found=True,
            profile_url=data.get("html_url", f"https://github.com/{username}"),
            name=data.get("name"),
            bio=data.get("bio"),
            company=data.get("company"),
            public_repos=data.get("public_repos", 0),
            followers=data.get("followers", 0),
            account_created_at=data.get("created_at"),
            top_languages=top_languages,
            most_recent_push=most_recent_push,
            notable_repos=notable_repos,
        )
