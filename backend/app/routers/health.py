"""Health endpoint that reports what the app can actually see.

The coachLLM writeup's costliest lesson: a bare "request failed" hid a chain of misconfigurations
(no Dockerfile detected, wrong service address, model not yet pulled) that cost hours to unwind.
This endpoint answers those questions directly instead of making the next person guess.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.llm.ollama_client import OllamaClient

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    client = OllamaClient()
    status = await client.health()
    return {
        "app": "ok",
        "ollama_url": settings.ollama_url,
        "model_name": settings.model_name,
        "ollama_reachable": status.reachable,
        "model_loaded": status.model_loaded,
        "models_available": status.models_available,
        "error": status.error,
    }
