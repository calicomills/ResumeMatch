"""The main pipeline endpoint: JD + resume in, full analysis out.

Wires together (in order): deterministic parsing -> LLM extraction -> deterministic scoring ->
LLM phrasing (questions, background summary). See module docstrings in each package for why the
split lands where it does.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.background_check.github_check import GithubProfile, check_github
from app.background_check.summarize import generate_background_summary
from app.background_check.website_check import WebsiteCheck, check_website
from app.config import settings
from app.llm.ollama_client import OllamaClient
from app.parsing.candidate_name import guess_candidate_name
from app.parsing.extract_text import FileTooLarge, UnsupportedFileType, extract_text_from_upload
from app.parsing.injection_scan import scan_for_injection_patterns
from app.parsing.links import ExtractedLink, extract_links
from app.parsing.pdf_integrity import HiddenTextSpan, extract_pdf_text_and_hidden_spans
from app.questions.generate import generate_questions
from app.scoring.match import compute_match
from app.skills.extract import extract_jd_requirements, extract_resume_profile

router = APIRouter()

MAX_GITHUB_CHECKED = 3
MAX_SITES_CHECKED = 3


async def _resolve_text(
    label: str, text: str | None, file: UploadFile | None, check_hidden_text: bool = False
) -> tuple[str, list[HiddenTextSpan], bool]:
    """Returns (text, hidden_spans, hidden_text_was_checked). hidden_spans is only ever
    non-empty when check_hidden_text=True and the upload was a PDF — that's the only channel
    this app currently knows how to hide text in (see parsing/pdf_integrity.py)."""
    if file is not None:
        content = await file.read()
        filename = file.filename or "upload.txt"
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413, detail=f"File exceeds {settings.max_upload_bytes // (1024 * 1024)}MB limit"
            )

        if check_hidden_text and filename.lower().endswith(".pdf"):
            try:
                extracted, hidden_spans = extract_pdf_text_and_hidden_spans(content)
            except Exception as exc:  # noqa: BLE001 - malformed/unreadable PDF
                raise HTTPException(status_code=400, detail=f"Could not read the {label} PDF: {exc}") from exc
            if not extracted.strip():
                raise HTTPException(status_code=400, detail=f"Could not extract any text from the {label} file.")
            return extracted, hidden_spans, True

        try:
            extracted = extract_text_from_upload(filename, content)
        except UnsupportedFileType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileTooLarge as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        if not extracted.strip():
            raise HTTPException(status_code=400, detail=f"Could not extract any text from the {label} file.")
        return extracted, [], False

    if text and text.strip():
        return text, [], False
    raise HTTPException(status_code=400, detail=f"Provide {label} text or upload a file.")


async def _gather_github(links: list[ExtractedLink]) -> list[GithubProfile]:
    if not links:
        return []
    return list(await asyncio.gather(*(check_github(l.username) for l in links if l.username)))


async def _gather_sites(links: list[ExtractedLink]) -> list[WebsiteCheck]:
    if not links:
        return []
    return list(await asyncio.gather(*(check_website(l.url) for l in links)))


@router.post("/analyze")
async def analyze(
    jd_text: str | None = Form(default=None),
    resume_text: str | None = Form(default=None),
    jd_file: UploadFile | None = File(default=None),
    resume_file: UploadFile | None = File(default=None),
) -> dict:
    jd_full_text, _jd_hidden_spans, _ = await _resolve_text("job description", jd_text, jd_file)
    # resume_full_text has any detected hidden text already stripped out — it never reaches the
    # LLM or any downstream parser. hidden_spans is reported to the recruiter separately below.
    resume_full_text, hidden_spans, hidden_text_checked = await _resolve_text(
        "resume", resume_text, resume_file, check_hidden_text=True
    )

    client = OllamaClient()
    candidate_name = guess_candidate_name(resume_full_text)

    injection_scan_text = resume_full_text + "\n" + "\n".join(s.text for s in hidden_spans)
    suspicious_phrases = scan_for_injection_patterns(injection_scan_text)

    links = extract_links(resume_full_text)
    github_links = [l for l in links if l.kind == "github"][:MAX_GITHUB_CHECKED]
    site_links = [l for l in links if l.kind == "site"][:MAX_SITES_CHECKED]
    linkedin_links = [l for l in links if l.kind == "linkedin"]

    jd_req, resume_profile, github_results, site_results = await asyncio.gather(
        extract_jd_requirements(client, jd_full_text),
        extract_resume_profile(client, resume_full_text),
        _gather_github(github_links),
        _gather_sites(site_links),
    )

    match_result = compute_match(jd_req, resume_profile)

    questions, background_summary = await asyncio.gather(
        generate_questions(client, match_result.gaps),
        generate_background_summary(client, github_results, site_results, candidate_name),
    )

    return {
        "candidate_name": candidate_name,
        "integrity": {
            "checked": hidden_text_checked,
            "hidden_text_found": len(hidden_spans) > 0,
            "hidden_text_spans": [asdict(s) for s in hidden_spans],
            "suspicious_phrases": suspicious_phrases,
        },
        "match": {
            "score": match_result.score,
            "required_matched": match_result.required_matched,
            "required_missing": match_result.required_missing,
            "nice_to_have_matched": match_result.nice_to_have_matched,
            "nice_to_have_missing": match_result.nice_to_have_missing,
            "experience_ok": match_result.experience_ok,
            "experience_detail": match_result.experience_detail,
            "education_ok": match_result.education_ok,
            "breakdown": match_result.breakdown,
        },
        "jd_requirements": asdict(jd_req),
        "resume_profile": asdict(resume_profile),
        "interview_questions": [asdict(q) for q in questions],
        "links": {
            "github": [asdict(l) for l in github_links],
            "linkedin": [asdict(l) for l in linkedin_links],
            "sites": [asdict(l) for l in site_links],
        },
        "background_check": {
            "github_profiles": [asdict(g) for g in github_results],
            "websites": [asdict(w) for w in site_results],
            "summary": background_summary,
        },
    }
