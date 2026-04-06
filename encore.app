{
  "id": "nexus-empire",
  "services": {
    "gateway": {
      "path": "gateway"
    },
    "users": {
      "path": "users"
    },
    "ai_engine": {
      "path": "ai_engine",
      "type": "container",
      "port": 8000,
      "healthCheck": "/health"
    }
  }
}