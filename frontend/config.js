// Central API config — reads from env var injected at build time by Vercel.
// Set VITE_API_URL in your Vercel project settings to:
//   https://nexus-backend-ffn4.onrender.com

const API_BASE = (
  window.__NEXUS_API_URL__ || 
  "https://nexus-backend-ffn4.onrender.com" // Your live Render Backend
);

window.NEXUS_API = API_BASE.replace(/\/$/, '') + "/api/v1";
window.STRIPE_PUBLIC_KEY = ""; 
window.GITHUB_CLIENT_ID = "";  
window.GOOGLE_CLIENT_ID = "";  
