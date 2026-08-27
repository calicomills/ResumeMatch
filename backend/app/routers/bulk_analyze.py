"""Bulk screening: one JD, many resumes, ranked by match score.

Deliberately does less per candidate than /api/analyze: it extracts the JD's requirements exactly
once (not once per resume — the same "don't ask the model something you already computed" rule
this app applies everywhere else) and, per resume, runs only skill/profile extraction and the
deterministic score. It skips interview-question generation and the GitHub/site background check,
since those are naturally a per-candidate follow-up once a recruiter has a shortlist, not
something worth an extra 2+ LLM calls and outbound HTTP requests for every resume in a batch of
fifty. The frontend re-runs /api/analyze for a single candidate on demand for that deeper view.

A bad file (corrupt PDF, unsupported type, empty after extraction) fails that one candidate, not
the whole batch — it's reported back with an `error` field instead of a match.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.llm.ollama_client import OllamaClient, OllamaClientProtocol
from app.parsing.candidate_name import guess_candidate_name
from app.parsing.injection_scan import scan_for_injection_patterns
from app.parsing.resolve_upload import resolve_text
from app.scoring.match import compute_match
from app.skills.extract import JDRequirements, extract_jd_requirements, extract_resume_profile

router = APIRouter()


@dataclass
class BulkCandidateResult:
    filename: str
    candidate_name: str | None = None
    score: int | None = None
    required_matched: list[str] = field(default_factory=list)
    required_missing: list[str] = field(default_factory=list)
    nice_to_have_matched: list[str] = field(default_factory=list)
    nice_to_have_missing: list[str] = field(default_factory=list)
    experience_ok: bool | None = None
    experience_detail: str = ""
    education_ok: bool | None = None
    years_experience: int | None = None
    resume_skills: list[str] = field(default_factory=list)
    hidden_text_found: bool = False
    suspicious_phrases_found: bool = False
    error: str | None = None


async def _process_one(
    client: OllamaClientProtocol,
    jd_req: JDRequirements,
    file: UploadFile,
    semaphore: asyncio.Semaphore,
) -> BulkCandidateResult:
    filename = file.filename or "resume"
    async with semaphore:
        try:
            resume_text, hidden_spans, _checked = await resolve_text(
                "resume", None, file, check_hidden_text=True
            )
        except HTTPException as exc:
            return BulkCandidateResult(filename=filename, error=str(exc.detail))

        candidate_name = guess_candidate_name(resume_text)
        scan_text = resume_text + "\n" + "\n".join(s.text for s in hidden_spans)
        suspicious_phrases = scan_for_injection_patterns(scan_text)

        resume_profile = await extract_resume_profile(client, resume_text)
        match_result = compute_match(jd_req, resume_profile)

        return BulkCandidateResult(
            filename=filename,
            candidate_name=candidate_name,
            score=match_result.score,
            required_matched=match_result.required_matched,
            required_missing=match_result.required_missing,
            nice_to_have_matched=match_result.nice_to_have_matched,
            nice_to_have_missing=match_result.nice_to_have_missing,
            experience_ok=match_result.experience_ok,
            experience_detail=match_result.experience_detail,
            education_ok=match_result.education_ok,
            years_experience=resume_profile.years_experience,
            resume_skills=resume_profile.skills,
            hidden_text_found=len(hidden_spans) > 0,
            suspicious_phrases_found=len(suspicious_phrases) > 0,
        )


@router.post("/bulk-analyze")
async def bulk_analyze(
    jd_text: str | None = Form(default=None),
    jd_file: UploadFile | None = File(default=None),
    resume_files: list[UploadFile] = File(default=[]),
) -> dict:
    if not resume_files:
        raise HTTPException(status_code=400, detail="Upload at least one resume file.")
    if len(resume_files) > settings.max_bulk_resumes:
        raise HTTPException(
            status_code=400,
            detail=f"Too many resumes: {len(resume_files)} uploaded, max is {settings.max_bulk_resumes}.",
        )

    jd_full_text, _hidden, _checked = await resolve_text("job description", jd_text, jd_file)

    client = OllamaClient()
    jd_req = await extract_jd_requirements(client, jd_full_text)

    semaphore = asyncio.Semaphore(settings.bulk_concurrency)
    results = await asyncio.gather(
        *(_process_one(client, jd_req, f, semaphore) for f in resume_files)
    )

    # Successful matches sorted best-first; anything that failed to parse goes last, in the
    # order it was uploaded, so a bad file doesn't get lost in the ranking silently.
    ranked = sorted(
        (r for r in results if r.error is None), key=lambda r: r.score, reverse=True  # type: ignore[arg-type]
    )
    failed = [r for r in results if r.error is not None]

    return {
        "jd_requirements": asdict(jd_req),
        "candidates": [asdict(r) for r in ranked],
        "failed": [asdict(r) for r in failed],
    }
