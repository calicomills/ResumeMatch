"""Phrase a short, factual summary of the already-fetched background-check data.

The model is handed exactly the facts we fetched and nothing else — it is never asked to
speculate about a candidate's GitHub or site beyond what was actually retrieved.
"""

from __future__ import annotations

import json

from app.background_check.github_check import GithubProfile
from app.background_check.website_check import WebsiteCheck
from app.llm.ollama_client import OllamaClientProtocol

SYSTEM = (
    "You write a short, neutral, factual summary for a recruiter based ONLY on the JSON facts "
    "given. Do not add anything not present in the JSON. 2-4 sentences, plain text, no markdown."
)

PROMPT_TEMPLATE = """Facts gathered about the candidate's public links:
{facts_json}

Write a short factual summary a recruiter can skim. Mention activity recency and notable
languages/repos if present. If a site was unreachable, say so plainly. Do not speculate.
"""


def _fallback_summary(github_profiles: list[GithubProfile], websites: list[WebsiteCheck]) -> str:
    parts: list[str] = []
    for gh in github_profiles:
        if gh.found:
            langs = ", ".join(gh.top_languages) or "no public language data"
            parts.append(
                f"GitHub ({gh.username}): {gh.public_repos} public repos, {gh.followers} followers, "
                f"top languages: {langs}."
            )
        else:
            parts.append(f"GitHub ({gh.username}): {gh.error or 'not found'}.")
    for site in websites:
        if site.reachable:
            parts.append(f"Site {site.url}: reachable" + (f", titled \"{site.title}\"." if site.title else "."))
        else:
            parts.append(f"Site {site.url}: unreachable ({site.error}).")
    return " ".join(parts) if parts else "No links found in the resume to check."


async def generate_background_summary(
    client: OllamaClientProtocol,
    github_profiles: list[GithubProfile],
    websites: list[WebsiteCheck],
) -> str:
    if not github_profiles and not websites:
        return "No GitHub or personal site links found in the resume."

    facts = {
        "github": [
            {
                "username": g.username,
                "found": g.found,
                "public_repos": g.public_repos,
                "followers": g.followers,
                "top_languages": g.top_languages,
                "most_recent_push": g.most_recent_push,
                "account_created_at": g.account_created_at,
                "notable_repos": g.notable_repos,
                "error": g.error,
            }
            for g in github_profiles
        ],
        "websites": [
            {
                "url": w.url,
                "reachable": w.reachable,
                "title": w.title,
                "description": w.description,
                "error": w.error,
            }
            for w in websites
        ],
    }

    fallback = _fallback_summary(github_profiles, websites)
    try:
        raw = await client.generate(
            PROMPT_TEMPLATE.format(facts_json=json.dumps(facts, indent=2)), SYSTEM
        )
    except Exception:  # noqa: BLE001 - Ollama unreachable/timeout: fall back, don't fail the request
        return fallback
    text = raw.strip()
    # Structural guard: if the model returned nothing usable, fall back to the templated summary
    # rather than retrying it.
    if not text or len(text) < 10:
        return fallback
    return text
