// Central API config — reads from env var injected at build time by Vercel.
// Set VITE_API_URL (or NEXT_PUBLIC_API_URL) in your Vercel project settings to:
//   https://your-nexus-backend.onrender.com
//
// For local dev, create a .env file:  VITE_API_URL=http://localhost:8000

const API_BASE = (
  window.__NEXUS_API_URL__ ||           // runtime injection (see index.html)
  "https://nexus-backend-ffn4.onrender.com"  // fallback: replace with your Render URL
);

window.NEXUS_API = API_BASE + "/api/v1";
