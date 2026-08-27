"""Thin wrapper around Ollama's HTTP API.

Two lessons from the coachLLM writeup are baked in here rather than left to callers:

1. "Do not argue with the model." We never loop pleading for well-formed JSON. We ask once,
   extract the first balanced JSON value from whatever came back (stripping code fences, stray
   prose, etc.), retry the raw call a bounded number of times on outright failure/timeout, and if
   we still don't have valid JSON we fall back to a caller-supplied default. The caller then
   degrades gracefully (e.g. a templated question) instead of the request blowing up.
2. Every failure mode is a typed, inspectable result — never a bare "request failed" — because
   that's the exact failure the writeup called out costing hours during the coachLLM deploy.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.config import settings


@dataclass
class HealthStatus:
    reachable: bool
    model_loaded: bool
    models_available: list[str] = field(default_factory=list)
    error: str | None = None


class OllamaClientProtocol(Protocol):
    """Interface both the real client and eval-harness fakes implement."""

    async def health(self) -> HealthStatus: ...

    async def generate(self, prompt: str, system: str | None = None) -> str: ...

    async def generate_json(
        self,
        prompt: str,
        system: str | None,
        default: Any,
    ) -> Any: ...


def extract_json(text: str) -> Any | None:
    """Pull the first balanced JSON object/array out of a model reply.

    Small instruct models routinely wrap JSON in ```json fences or add a sentence before/after
    it. Rather than re-prompting to fix that, we just find the JSON ourselves.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = None
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start is None:
        return None

    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.model = model or settings.model_name
        self.timeout = timeout or settings.llm_timeout_seconds

    async def health(self) -> HealthStatus:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001 - surfaced verbatim to /api/health
            return HealthStatus(reachable=False, model_loaded=False, error=f"{type(exc).__name__}: {exc}")

        models = [m.get("name", "") for m in data.get("models", [])]
        # Ollama tags responses include the ":latest" suffix sometimes; compare loosely.
        model_loaded = any(m == self.model or m.startswith(self.model.split(":")[0] + ":") for m in models)
        return HealthStatus(reachable=True, model_loaded=model_loaded, models_available=models)

    async def _call(self, prompt: str, system: str | None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": settings.llm_temperature},
        }
        if system:
            payload["system"] = system

        last_error: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                    resp.raise_for_status()
                    return resp.json().get("response", "")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
        raise RuntimeError(f"Ollama call failed after {settings.llm_max_retries + 1} attempts: {last_error}")

    async def generate(self, prompt: str, system: str | None = None) -> str:
        return await self._call(prompt, system)

    async def generate_json(self, prompt: str, system: str | None, default: Any) -> Any:
        """Generate and parse JSON. On any failure (timeout, malformed output), return `default`
        rather than retrying the model with a firmer instruction — the writeup's lesson that a
        1.5B model won't reliably self-correct, so the fallback is structural, not conversational.
        """
        try:
            raw = await self._call(prompt, system)
        except Exception:
            return default
        parsed = extract_json(raw)
        return parsed if parsed is not None else default
