"""Turn uploaded files (or pasted text) into plain text.

Deliberately dumb and deterministic — no LLM involved. The model never sees raw bytes, only text.

Two guards here exist purely against adversarial input, not normal resumes:
- PDFs are capped at `max_pdf_pages` — a real resume is never remotely close to that, so this
  only ever bites a file trying to make parsing pathologically slow (silently truncated rather
  than rejected outright, so a legitimately long multi-page portfolio still gets *something*
  rather than an error).
- DOCX files are zip archives; `_extract_docx` checks the archive's *declared uncompressed size*
  before asking python-docx to actually inflate it, so a small "zip bomb" .docx (tiny on disk,
  huge once decompressed) is rejected before it can exhaust memory.
"""

from __future__ import annotations

import io
import zipfile

import docx
import pdfplumber

from app.config import settings


class UnsupportedFileType(Exception):
    pass


class FileTooLarge(Exception):
    pass


def extract_text_from_upload(filename: str, content: bytes) -> str:
    if len(content) > settings.max_upload_bytes:
        raise FileTooLarge(f"File exceeds {settings.max_upload_bytes // (1024*1024)}MB limit")

    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(content)
    if lower.endswith(".docx"):
        return _extract_docx(content)
    if lower.endswith((".txt", ".md")):
        return content.decode("utf-8", errors="ignore")
    raise UnsupportedFileType(f"Unsupported file type: {filename}. Use PDF, DOCX, or TXT.")


def _extract_pdf(content: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages[: settings.max_pdf_pages]:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def _check_docx_not_a_zip_bomb(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile as exc:
        raise UnsupportedFileType("This .docx file is not a valid document.") from exc

    if total_uncompressed > settings.max_docx_uncompressed_bytes:
        raise FileTooLarge(
            f"This .docx file expands to over {settings.max_docx_uncompressed_bytes // (1024 * 1024)}MB "
            "when decompressed and was rejected."
        )


def _extract_docx(content: bytes) -> str:
    _check_docx_not_a_zip_bomb(content)
    document = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs).strip()
