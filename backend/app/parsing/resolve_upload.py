"""Shared "pasted text or uploaded file" resolution, used by both the single-candidate and bulk
analyze endpoints so the size limits, error handling, and hidden-text check path only live once.
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.parsing.extract_text import FileTooLarge, UnsupportedFileType, extract_text_from_upload
from app.parsing.pdf_integrity import HiddenTextSpan, extract_pdf_text_and_hidden_spans


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
