"""Turn uploaded files (or pasted text) into plain text.

Deliberately dumb and deterministic — no LLM involved. The model never sees raw bytes, only text.
"""

from __future__ import annotations

import io

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
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def _extract_docx(content: bytes) -> str:
    document = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs).strip()
