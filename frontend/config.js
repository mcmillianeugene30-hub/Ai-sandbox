// Central API config — reads from env var injected at build time by Vercel.
// Set VITE_API_URL (or NEXT_PUBLIC_API_URL) in your Vercel project settings to:
//   https://your-nexus-backend.onrender.com
//
// For local dev, create a .env file:  VITE_API_URL=http://localhost:8000

const API_BASE = (
  window.__NEXUS_API_URL__ || 
  (window.location.hostname.includes('vercel.app') ? '' : 'https://nexus-backend-ffn4.onrender.com')
);

window.NEXUS_API = (API_BASE.replace(/\/$/, '') || '') + "/api/v1";
window.STRIPE_PUBLIC_KEY = ""; // Set in Vercel Env
window.GITHUB_CLIENT_ID = "";  // Set in Vercel Env
window.GOOGLE_CLIENT_ID = "";  // Set in Vercel Env
