"""Request-level guardrails that need to run before any route/parsing code sees the request body.

The per-file and per-field size checks in parsing/resolve_upload.py run *after* Starlette has
already read a field into memory — fine for catching one oversized file, but not for an
aggregate-sized request (e.g. many files each just under the per-file cap, or a bulk upload with
an excessive file count driving total size up). This middleware rejects an oversized request
before the body is read at all, whenever the client sends Content-Length — and falls back to
counting bytes as they stream in for the chunked-transfer-encoding case, where Content-Length
isn't sent up front and a header-only check could otherwise be bypassed.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class _RequestTooLarge(Exception):
    pass


class MaxBodySizeMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > self.max_bytes:
                await self._reject(scope, receive, send)
                return

        total = 0

        async def counting_receive():
            nonlocal total
            message = await receive()
            if message.get("type") == "http.request":
                total += len(message.get("body") or b"")
                if total > self.max_bytes:
                    raise _RequestTooLarge()
            return message

        try:
            await self.app(scope, counting_receive, send)
        except _RequestTooLarge:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            {"detail": f"Request body exceeds {self.max_bytes // (1024 * 1024)}MB limit"},
            status_code=413,
        )
        await response(scope, receive, send)
