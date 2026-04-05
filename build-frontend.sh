#!/bin/bash
# Vercel Build Script for Project Nexus Frontend
# This script injects environment variables into config.js at build time.

CONFIG_FILE="frontend/config.js"

echo "==> Injecting Vercel Environment Variables into $CONFIG_FILE"

if [ -n "$VITE_API_URL" ]; then
  sed -i "s|window.__NEXUS_API_URL__ = .*|window.__NEXUS_API_URL__ = \"$VITE_API_URL\";|g" frontend/index.html || true
fi

if [ -n "$STRIPE_PUBLIC_KEY" ]; then
  sed -i "s|window.STRIPE_PUBLIC_KEY = .*|window.STRIPE_PUBLIC_KEY = \"$STRIPE_PUBLIC_KEY\";|g" $CONFIG_FILE
fi

if [ -n "$GITHUB_CLIENT_ID" ]; then
  sed -i "s|window.GITHUB_CLIENT_ID = .*|window.GITHUB_CLIENT_ID = \"$GITHUB_CLIENT_ID\";|g" $CONFIG_FILE
fi

if [ -n "$GOOGLE_CLIENT_ID" ]; then
  sed -i "s|window.GOOGLE_CLIENT_ID = .*|window.GOOGLE_CLIENT_ID = \"$GOOGLE_CLIENT_ID\";|g" $CONFIG_FILE
fi

echo "==> Build complete"
