#!/bin/sh
# Serve Ollama and make sure the configured model is pulled. Pulling is idempotent — once the
# model is cached on the attached volume, restarts are fast; only the very first boot pays the
# download cost.
set -e

ollama serve &
SERVE_PID=$!

until ollama list >/dev/null 2>&1; do
  sleep 1
done

MODEL="${MODEL_NAME:-qwen2.5:1.5b-instruct}"
echo "Ensuring model is present: ${MODEL}"
ollama pull "${MODEL}"

wait "${SERVE_PID}"
