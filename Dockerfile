FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
ENV PYTHONPATH=/app/src

RUN pip install --no-cache-dir ".[azure]"

# Sensible hosted defaults; override with -e / container env vars.
ENV BRIDGE_TRANSPORT=http \
    BRIDGE_HOST=0.0.0.0 \
    BRIDGE_PORT=8000

EXPOSE 8000
CMD ["python", "-m", "bridge.server"]
