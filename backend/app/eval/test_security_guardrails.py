"""Tests for the file-size / timeout / resource-exhaustion guardrails: aggregate request size,
pasted-text size, DOCX zip-bomb detection, PDF page-count cap, and parsing timeouts.
"""

from __future__ import annotations

import asyncio
import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

import app.routers.analyze as analyze_module
from app.config import settings
from app.eval.fakes import FakeOllamaClient
from app.main import app
from app.middleware import MaxBodySizeMiddleware
from app.parsing.extract_text import FileTooLarge, UnsupportedFileType, _check_docx_not_a_zip_bomb
from app.parsing.resolve_upload import resolve_text


@pytest.fixture
def client(monkeypatch):
    fake = FakeOllamaClient()
    monkeypatch.setattr(analyze_module, "OllamaClient", lambda: fake)
    return TestClient(app)


# --- Aggregate request size (middleware) ---------------------------------------------------


def test_max_body_size_middleware_rejects_by_content_length():
    async def handler(request):
        return PlainTextResponse("ok")

    test_app = Starlette(routes=[Route("/", handler, methods=["POST"])])
    test_app.add_middleware(MaxBodySizeMiddleware, max_bytes=10)

    with TestClient(test_app) as c:
        resp = c.post("/", content=b"x" * 11)
        assert resp.status_code == 413


def test_max_body_size_middleware_allows_under_limit():
    async def handler(request):
        return PlainTextResponse("ok")

    test_app = Starlette(routes=[Route("/", handler, methods=["POST"])])
    test_app.add_middleware(MaxBodySizeMiddleware, max_bytes=1000)

    with TestClient(test_app) as c:
        resp = c.post("/", content=b"x" * 10)
        assert resp.status_code == 200


def test_analyze_endpoint_rejects_oversized_request_before_parsing(client):
    # A request whose declared Content-Length exceeds max_request_bytes should be rejected by the
    # middleware, well before any file parsing happens.
    huge = b"x" * (settings.max_request_bytes + 1024)
    resp = client.post(
        "/api/analyze",
        files={"resume_file": ("resume.txt", huge, "text/plain")},
        data={"jd_text": "some JD"},
    )
    assert resp.status_code == 413


# --- Pasted-text size cap --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_text_rejects_oversized_pasted_text(monkeypatch):
    monkeypatch.setattr(settings, "max_text_field_bytes", 100)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await resolve_text("resume", "x" * 200, None)
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_resolve_text_allows_pasted_text_under_cap(monkeypatch):
    monkeypatch.setattr(settings, "max_text_field_bytes", 100)
    text, spans, checked = await resolve_text("resume", "short resume text", None)
    assert text == "short resume text"
    assert spans == []
    assert checked is False


def test_analyze_endpoint_rejects_oversized_pasted_text_field(client, monkeypatch):
    monkeypatch.setattr(settings, "max_text_field_bytes", 100)
    resp = client.post("/api/analyze", data={"jd_text": "job description", "resume_text": "x" * 500})
    assert resp.status_code == 413


# --- DOCX zip-bomb guard ----------------------------------------------------------------------


def _make_docx_like_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_docx_zip_bomb_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "max_docx_uncompressed_bytes", 1000)
    # Highly compressible content — small on disk, "huge" once decompressed relative to our cap.
    bomb = _make_docx_like_zip({"word/document.xml": b"A" * 5000})
    with pytest.raises(FileTooLarge):
        _check_docx_not_a_zip_bomb(bomb)


def test_normal_sized_docx_passes_the_check(monkeypatch):
    monkeypatch.setattr(settings, "max_docx_uncompressed_bytes", 1_000_000)
    small = _make_docx_like_zip({"word/document.xml": b"<xml>hello</xml>"})
    _check_docx_not_a_zip_bomb(small)  # should not raise


def test_invalid_zip_is_rejected_as_unsupported():
    with pytest.raises(UnsupportedFileType):
        _check_docx_not_a_zip_bomb(b"not actually a zip file")


# --- Parsing timeout ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_timeout_returns_408_not_a_hang(monkeypatch):
    from fastapi import HTTPException

    from app.parsing import resolve_upload

    monkeypatch.setattr(settings, "file_parse_timeout_seconds", 0.05)

    def slow_parser(_content: bytes):
        import time

        time.sleep(1)  # simulate a pathological/hung parse
        return "should never get here"

    monkeypatch.setattr(resolve_upload, "extract_text_from_upload", lambda filename, content: slow_parser(content))

    with pytest.raises(HTTPException) as exc_info:
        await resolve_upload.resolve_text(
            "resume",
            None,
            _fake_upload_file("resume.txt", b"whatever"),
        )
    assert exc_info.value.status_code == 408


class _FakeUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


def _fake_upload_file(filename: str, content: bytes) -> _FakeUploadFile:
    return _FakeUploadFile(filename, content)
