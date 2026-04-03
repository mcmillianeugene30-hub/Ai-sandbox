#!/bin/bash
# Render build script — runs from repo root
set -e
echo "==> Installing dependencies from root requirements.txt"
pip install --upgrade pip
pip install -r requirements.txt
echo "==> Build complete"
