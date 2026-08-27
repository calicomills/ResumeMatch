"""Shared "pasted text or uploaded file" resolution, used by both the single-candidate and bulk
analyze endpoints so the size limits, error handling, and hidden-text check path only live once.

Two guardrails live here specifically:
- Parsing (pdfplumber/python-docx) is CPU-bound and synchronous. Running it directly in an
  `async def` route handler blocks the whole event loop — every other in-flight request on this
  worker stalls until it finishes, not just the one being parsed. A single malformed or
  adversarially-crafted file (see parsing/extract_text.py and parsing/pdf_integrity.py for the
  zip-bomb/page-count guards on the content itself) could otherwise take the entire server down,
  not just fail its own request. `asyncio.to_thread` moves it off the event loop; `asyncio.wait_for`
  bounds how long the request waits for it. Note the caveat below on what the timeout does and
  doesn't guarantee.
- Pasted-text fields (jd_text/resume_text) have no file attached, so the file-size check never
  runs for them — without a separate cap here, that's an unbounded-size text field.
"""

from __future__ import annotations

import asyncio

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.parsing.extract_text import FileTooLarge, UnsupportedFileType, extract_text_from_upload
from app.parsing.pdf_integrity import HiddenTextSpan, extract_pdf_text_and_hidden_spans


async def _parse_with_timeout(label: str, func, *args):
    """Runs a synchronous parser in a worker thread with a hard wall-clock timeout.

    Caveat: `asyncio.wait_for` timing out makes *this request* fail promptly, but Python can't
    forcibly kill a running thread — if `func` is truly stuck (not just slow), the orphaned thread
    keeps running in the background until it finishes on its own. This bounds how long a client
    waits and keeps the server responsive to other requests either way; it isn't a guarantee that
    every CPU cycle from a malicious file is reclaimed immediately. The page-count/decompressed-size
    caps on the content itself (extract_text.py, pdf_integrity.py) are what keep a single parse
    from being pathological in the first place.
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args), timeout=settings.file_parse_timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=408,
            detail=f"Timed out reading the {label} file — it may be corrupt or unusually complex.",
        ) from exc


async def resolve_text(
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
                extracted, hidden_spans = await _parse_with_timeout(
                    label, extract_pdf_text_and_hidden_spans, content
                )
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001 - malformed/unreadable PDF
                raise HTTPException(status_code=400, detail=f"Could not read the {label} PDF: {exc}") from exc
            if not extracted.strip():
                raise HTTPException(status_code=400, detail=f"Could not extract any text from the {label} file.")
            return extracted, hidden_spans, True

        try:
            extracted = await _parse_with_timeout(label, extract_text_from_upload, filename, content)
        except HTTPException:
            raise
        except UnsupportedFileType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileTooLarge as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        if not extracted.strip():
            raise HTTPException(status_code=400, detail=f"Could not extract any text from the {label} file.")
        return extracted, [], False

    if text and text.strip():
        if len(text.encode("utf-8", errors="ignore")) > settings.max_text_field_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Pasted {label} text exceeds {settings.max_text_field_bytes // 1024}KB limit — upload it as a file instead.",
            )
        return text, [], False
    raise HTTPException(status_code=400, detail=f"Provide {label} text or upload a file.")
