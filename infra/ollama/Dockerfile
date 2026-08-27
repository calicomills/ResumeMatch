# Deployed as its own Railway service (root directory: infra/ollama). Explicit Dockerfile +
# railway.json here too, for the same reason as backend/Dockerfile: don't let the platform guess.
FROM ollama/ollama:latest
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
