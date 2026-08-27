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
    max_upload_bytes: int = 5 * 1024 * 1024  # 5MB, enforced per file
    max_text_field_bytes: int = 300 * 1024  # 300KB, enforced on pasted jd_text/resume_text (no file involved)
    max_bulk_resumes: int = 50
    bulk_concurrency: int = 3  # bounded so a big batch doesn't hammer a single self-hosted Ollama

    # Rejected before Starlette even parses the multipart body — the per-file/per-field checks
    # above run after a field is already read into memory, so this is the first line of defense
    # against an oversized request in aggregate (e.g. many files each just under the per-file cap).
    max_request_bytes: int = 60 * 1024 * 1024  # 60MB

    # A malformed/adversarial file (zip bomb, pathological PDF structure) can make parsing take
    # far longer than any legitimate resume would. This bounds how long a single upload's parsing
    # is allowed to run before the request fails cleanly instead of hanging.
    file_parse_timeout_seconds: float = 20.0
    max_pdf_pages: int = 20  # resumes are essentially never longer than this
    max_docx_uncompressed_bytes: int = 50 * 1024 * 1024  # guards against a small zip-bomb .docx

    # Optional: raises GitHub API rate limit from 60/hr to 5000/hr if set
    github_token: str | None = None

    # Background-check site fetch limits
    site_fetch_timeout_seconds: float = 6.0
    site_fetch_max_bytes: int = 512 * 1024

    # CORS: comma-separated origins, "*" for dev
    cors_origins: str = "*"


settings = Settings()
