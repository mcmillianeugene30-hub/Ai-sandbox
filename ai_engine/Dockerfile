# ── Stage 1: base ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git sqlite3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Stage 2: dependencies ──────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ── Stage 3: final ─────────────────────────────────────────────────────────────
FROM deps AS final

# Copy all source code
COPY . /app

# Create runtime directories
RUN mkdir -p /app/nexus-ai-os/projects \
             /app/nexus-ai-os/memory_db \
             /app/backend/uploads \
             /app/backend/chroma_db

# Set working dir to backend (where uvicorn runs)
WORKDIR /app/backend

EXPOSE 8000

ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
