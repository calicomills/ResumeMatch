"""Deterministic extraction + classification of links found in a resume.

No LLM involved: which links exist and what kind they are is a fact we can read off the text
ourselves, not something worth spending a model call on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

# Matches URLs with or without a scheme, and bare "domain.tld/path" forms resumes commonly use
# (e.g. "github.com/janedoe", "janedoe.dev").
_URL_RE = re.compile(
    r"""(?xi)
    \b
    (?:https?://)?
    (?:www\.)?
    (
        [a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?
        (?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+
    )
    (/[^\s,;()<>\[\]"']*)?
    """
)

# Domains that show up in resumes but aren't meaningful "links" for a background check —
# including degree abbreviations that happen to collide with real TLDs (reported bug: "B.Tech"
# parsed as a link to b.tech and background-checked, because .tech is a real TLD in
# _KNOWN_TLDS_HINT below; the same collision exists for "B.Com"/"M.Com" against .com).
_IGNORE_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "fonts.googleapis.com",
    "schema.org",
    "b.tech",
    "m.tech",
    "b.com",
    "m.com",
}

_KNOWN_TLDS_HINT = re.compile(r"\.(com|org|net|io|dev|me|co|in|ai|app|tech|xyz|info|us|uk|ca)$", re.I)


@dataclass
class ExtractedLink:
    url: str
    domain: str
    kind: str  # "github" | "linkedin" | "site"
    username: str | None = None


def _normalize(domain: str, path: str | None) -> str:
    path = path or ""
    return f"https://{domain}{path}".rstrip("/")


def extract_links(text: str) -> list[ExtractedLink]:
    seen: set[str] = set()
    results: list[ExtractedLink] = []

    for match in _URL_RE.finditer(text):
        domain = match.group(1).lower()
        path = match.group(2) or ""

        if domain in _IGNORE_DOMAINS:
            continue
        if not _KNOWN_TLDS_HINT.search(domain):
            continue
        # Skip bare-word false positives like "e.g." or version numbers that slipped through.
        if domain.count(".") == 0:
            continue

        url = _normalize(domain, path)
        if url in seen:
            continue
        seen.add(url)

        if "github.com" in domain:
            username = path.strip("/").split("/")[0] if path.strip("/") else None
            if username and username.lower() not in {"orgs", "topics", "sponsors"}:
                results.append(ExtractedLink(url=url, domain=domain, kind="github", username=username))
            continue

        if "linkedin.com" in domain:
            results.append(ExtractedLink(url=url, domain=domain, kind="linkedin"))
            continue

        results.append(ExtractedLink(url=url, domain=domain, kind="site"))

    return results


def parse_domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower()
