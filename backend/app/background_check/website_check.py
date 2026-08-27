"""Lightweight, safe check of a personal-site link found in a resume.

We only ever fetch the URL literally present in the resume (the candidate's own claim about
themselves), with a short timeout and a byte cap, and we only read <title>/meta description —
never execute scripts or follow the page's own links. This is a reachability + metadata check,
not a scrape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.config import settings

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.IGNORECASE | re.DOTALL
)


@dataclass
class WebsiteCheck:
    url: str
    reachable: bool
    status_code: int | None = None
    final_url: str | None = None
    title: str | None = None
    description: str | None = None
    error: str | None = None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:300]


async def check_website(url: str) -> WebsiteCheck:
    try:
        async with httpx.AsyncClient(
            timeout=settings.site_fetch_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ResumeSmash-App (recruiter background check)"},
        ) as client:
            async with client.stream("GET", url) as resp:
                chunks = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= settings.site_fetch_max_bytes:
                        break
                body = b"".join(chunks).decode("utf-8", errors="ignore")

                if resp.status_code >= 400:
                    return WebsiteCheck(
                        url=url, reachable=False, status_code=resp.status_code,
                        final_url=str(resp.url), error=f"HTTP {resp.status_code}",
                    )

                title_match = _TITLE_RE.search(body)
                desc_match = _DESC_RE.search(body)
                return WebsiteCheck(
                    url=url,
                    reachable=True,
                    status_code=resp.status_code,
                    final_url=str(resp.url),
                    title=_clean(title_match.group(1)) if title_match else None,
                    description=_clean(desc_match.group(1)) if desc_match else None,
                )
    except Exception as exc:  # noqa: BLE001
        return WebsiteCheck(url=url, reachable=False, error=f"{type(exc).__name__}: {exc}")
