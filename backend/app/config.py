"""Central config, all overridable via env vars so local/docker-compose/Railway behave the same.

Lesson from the coachLLM writeup: the deploy broke silently multiple times because nothing
reported what the app could actually see. Keeping every knob here (and echoed by /api/health)
is what makes that diagnosable instead of a mystery "request failed".
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    # Ollama connection. In docker-compose this is http://ollama:11434, on Railway it's the
    # private-networking address of the ollama service, e.g. http://ollama.railway.internal:11434.
    ollama_url: str = "http://localhost:11434"
    model_name: str = "qwen2.5:1.5b-instruct"

    # LLM call behavior
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2
    llm_temperature: float = 0.2

    # Upload limits
    max_upload_bytes: int = 5 * 1024 * 1024  # 5MB

    # Optional: raises GitHub API rate limit from 60/hr to 5000/hr if set
    github_token: str | None = None

    # Background-check site fetch limits
    site_fetch_timeout_seconds: float = 6.0
    site_fetch_max_bytes: int = 512 * 1024

    # CORS: comma-separated origins, "*" for dev
    cors_origins: str = "*"


settings = Settings()
