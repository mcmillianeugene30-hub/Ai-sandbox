"""
Project Nexus Backend Entry Point
This file exists for backward compatibility. The main app is defined in app.py.
"""
from backend.app import app

# Re-export the app for uvicorn
# Usage: uvicorn backend.main:app --host 0.0.0.0 --port 8000

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
