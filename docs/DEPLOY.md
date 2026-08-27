# Deploying ResumeMatch

Two Railway services in one project: `ollama` (the model, self-hosted) and `app` (FastAPI + the
built React frontend, served from one container). The `app` service is public; `ollama` is not.

## 1. Local first (recommended before touching Railway)

```bash
docker compose up --build
```

This will pull `qwen2.5:1.5b-instruct` on first run (~1GB download) — only do this if you're
online and fine with that download. Once it's up:

- `http://localhost:8000/api/health` should report `ollama_reachable: true, model_loaded: true`.
- `http://localhost:8000/` serves the app itself.

If `/api/health` shows `ollama_reachable: false`, the `error` field tells you exactly what failed
— that endpoint exists specifically so you never see a bare "request failed" (a real pain point
from the coachLLM writeup this project's patterns are based on).

## 2. Railway: `ollama` service

1. New Service → Deploy from GitHub repo → select this repo.
2. Settings → set **Root Directory** to `infra/ollama`. Railway will pick up
   `infra/ollama/railway.json`, which pins the Dockerfile builder explicitly (don't rely on
   autodetect — it's what broke the original coachLLM deploy).
3. Settings → Volumes → add a volume mounted at `/root/.ollama` (a few GB — the default model is
   ~1GB, leave headroom if you switch to a bigger one later). Without this, every restart re-pulls
   the model from scratch.
4. Optional: set env var `MODEL_NAME` if you want something other than the default
   `qwen2.5:1.5b-instruct` (see "Choosing a model" below).
5. Deploy. First boot pulls the model — watch the deploy logs, it can take a few minutes. Do **not**
   generate a public domain for this service; it only needs to be reachable from `app` over
   Railway's private network.
6. Once deployed, note this service's private hostname: Settings → Networking → it's
   `<service-name>.railway.internal`, port `11434`.

## 3. Railway: `app` service

1. New Service → Deploy from GitHub repo → same repo, **Root Directory** left at `/` (repo root),
   so Railway picks up the top-level `railway.json` (→ `backend/Dockerfile`, which builds the
   frontend and bundles it into the FastAPI image).
2. Env vars:
   - `OLLAMA_URL` = `http://<ollama-service-name>.railway.internal:11434`
   - `MODEL_NAME` = same value you set (or left default) on the `ollama` service — these must match.
   - `GITHUB_TOKEN` (optional) — raises the GitHub background-check API limit from 60/hr to
     5000/hr. Only needed if you expect heavy usage.
3. Settings → Networking → Generate Domain. This is the one public URL for the whole app.
4. Deploy, then visit `https://<app-domain>/api/health` before trying the UI — confirm
   `ollama_reachable` and `model_loaded` are both `true`. If not, the `error` field says why
   (wrong `OLLAMA_URL`, `ollama` service still pulling, etc.) — check that before anything else.

## Choosing a model

Default is `qwen2.5:1.5b-instruct` — small enough to run acceptably on Railway's CPU-only hobby
tier. If you have more RAM/CPU available and want better extraction/question quality, bump
`MODEL_NAME` on both services to `qwen2.5:3b-instruct` (or similar) and redeploy the `ollama`
service so it pulls the new model.

Don't point this at a `-coder` variant (e.g. `qwen2.5-coder`) — it's tuned for code completion,
not the extraction/phrasing tasks this app actually needs; in testing it noticeably confused JD
requirement categories that a plain instruct model got right.

## Updating

Push to the branch each service tracks; Railway rebuilds automatically. The `ollama` service only
needs a fresh pull if `MODEL_NAME` changes — otherwise redeploys reuse the volume and start fast.
