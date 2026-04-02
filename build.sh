#!/bin/bash
# Render build script — runs from repo root regardless of Root Directory setting
set -e
echo "==> Installing dependencies from backend/requirements.txt"
pip install -r backend/requirements.txt
echo "==> Build complete"
