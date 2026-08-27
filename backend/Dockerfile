# Build context is the repo root (see docker-compose.yml / docs/DEPLOY.md) — this Dockerfile
# needs both frontend/ and backend/ to produce a single container that serves the built React
# app as static files from FastAPI.
#
# Explicit multi-stage Dockerfile on purpose: the coachLLM writeup's deploy broke silently the
# first time because the platform tried to autodetect a build instead of using the Dockerfile.
# railway.json pins builder=DOCKERFILE so that never happens here.

FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./app/static

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Railway (and most PaaS) inject $PORT at runtime; default to 8000 for local/docker-compose use.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
