// Central API config for Encore Cloud
const API_BASE = (
  window.__NEXUS_API_URL__ ||
  (window.location.hostname.includes('encoreapi.com') ? '' : 'http://localhost:4000')
);

window.NEXUS_API = (API_BASE.replace(/\/$/, '') || '') + ""; 
window.STRIPE_PUBLIC_KEY = "";
window.GITHUB_CLIENT_ID = "";
window.GOOGLE_CLIENT_ID = "";
