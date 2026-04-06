# ── Stage 1: base ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git sqlite3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Stage 2: dependencies ──────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 3: final ─────────────────────────────────────────────────────────────
FROM deps AS final

# Copy all source code (from ai_engine context)
COPY . .

# Create runtime directories
RUN mkdir -p projects \
             memory_db \
             uploads \
             chroma_db

EXPOSE 8000

ENV PYTHONPATH=/app

# main:app refers to main.py in the root of the context
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
