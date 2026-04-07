// Central API config for Project Nexus v10.3 (Pure Encore)
const API_BASE = (
  window.__NEXUS_API_URL__ ||
  (window.location.hostname.includes('encoreapi.com') ? '' : 'http://localhost:4000')
);

// We use /api/v1 as the base for all Encore and Proxied endpoints
window.NEXUS_API = (API_BASE.replace(/\/$/, '') || '') + "/api/v1";

window.STRIPE_PUBLIC_KEY = "";
window.GITHUB_CLIENT_ID = "";
window.GOOGLE_CLIENT_ID = "";
