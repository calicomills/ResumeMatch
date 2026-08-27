"""A scripted fake Ollama client for the eval harness.

Straight application of the writeup's "you cannot tune what you cannot measure" lesson: tests
replay controlled model responses (including deliberately malformed ones) through the real
extraction/scoring/question code and assert on what the API actually returns — not on whether an
LLM call merely happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.llm.ollama_client import HealthStatus


@dataclass
class FakeOllamaClient:
    jd_response: Any = None
    resume_response: Any = None
    questions_response: Any = None
    generate_text: str = "This candidate has an active GitHub profile with recent contributions."
    raise_on_generate: bool = False
    reachable: bool = True
    model_loaded: bool = True
    jd_extraction_calls: int = 0
    resume_extraction_calls: int = 0

    async def health(self) -> HealthStatus:
        return HealthStatus(
            reachable=self.reachable,
            model_loaded=self.model_loaded,
            models_available=["fake-model:latest"] if self.model_loaded else [],
        )

    async def generate(self, prompt: str, system: str | None = None) -> str:
        if self.raise_on_generate:
            raise RuntimeError("simulated Ollama failure")
        return self.generate_text

    async def generate_json(self, prompt: str, system: str | None, default: Any) -> Any:
        # Route based on distinguishing substrings in each module's prompt template, so call
        # ordering under asyncio.gather doesn't matter.
        if "min_years_experience" in prompt:
            self.jd_extraction_calls += 1
            return self.jd_response if self.jd_response is not None else default
        if "years_experience" in prompt:
            self.resume_extraction_calls += 1
            return self.resume_response if self.resume_response is not None else default
        if "Write exactly" in prompt:
            return self.questions_response if self.questions_response is not None else default
        return default
