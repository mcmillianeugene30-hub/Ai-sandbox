#!/bin/bash
# Nexus AI-OS Cloud Deployment Script

echo "🚀 Starting Nexus AI-OS Cloud Deployment..."

# 1. Environment Check
if [ -z "$GROQ_API_KEY" ]; then
    echo "❌ Error: GROQ_API_KEY is not set. Please set it in your environment."
    exit 1
fi

# 2. Build and Start Docker
echo "🐳 Building Docker Containers..."
docker-compose up -d --build

# 3. Status Check
echo "🔍 Checking System Status..."
sleep 5
curl -s http://localhost:8000/api/v1/models > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Backend is ONLINE."
else
    echo "❌ Backend is OFFLINE. Check 'docker-compose logs'."
fi

echo "---"
echo "🌐 Nexus Dashboard: http://localhost:8080/nexus/dashboard.html"
echo "🌐 Sandbox Playground: http://localhost:8080/index.html"
echo "🔑 Admin Credentials: nexus / nexus2026"
echo "🚀 Deployment Complete!"
