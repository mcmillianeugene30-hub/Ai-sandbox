# 🚀 Deploying Project Nexus — Vercel (Frontend) + Render (Backend)

## Architecture

```
Vercel (Static CDN)           Render (Python FastAPI)
┌───────────────────┐         ┌──────────────────────────────┐
│ /                 │         │ POST /api/v1/auth/login        │
│ /pricing          │──HTTPS─▶│ GET  /api/v1/billing/plans    │
│ /nexus/dashboard  │         │ GET  /api/v1/admin/stats      │
│ /admin            │         │ GET  /api/v1/nexus/app-build  │
└───────────────────┘         └──────────────────────────────┘
```

---

## Step 1 — Deploy Backend to Render

### A. Create a new Web Service on Render
1. Go to [render.com](https://render.com) → **New → Web Service**
2. Connect your GitHub repo: `mcmillianeugene30-hub/Ai-sandbox`
3. Use these settings:

| Setting | Value |
|---|---|
| **Root Directory** | `backend` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | Free (or Starter $7/mo for always-on) |

### B. Add Environment Variables in Render Dashboard
Go to **Environment** tab and add:

```
GROQ_API_KEY        = gsk_YOUR_GROQ_API_KEY_HERE
GEMINI_API_KEY      = AIzaSy_YOUR_GEMINI_API_KEY_HERE
OPENROUTER_API_KEY  = sk-or-v1-YOUR_OPENROUTER_KEY_HERE
FRONTEND_URL        = https://YOUR-PROJECT.vercel.app
```

### C. Add a Disk (for SQLite persistence)
Go to **Disks** tab:
- **Name:** `nexus-data`
- **Mount Path:** `/opt/render/project/src/data`
- **Size:** 1 GB

### D. Get your Render URL
After deploy, your backend URL will be:
```
https://nexus-backend-xxxx.onrender.com
```

---

## Step 2 — Deploy Frontend to Vercel

### A. Import project on Vercel
1. Go to [vercel.com](https://vercel.com) → **New Project**
2. Import `mcmillianeugene30-hub/Ai-sandbox` from GitHub
3. **Root Directory:** leave as `/` (repo root)
4. **Framework Preset:** Other (Static)
5. **Output Directory:** `frontend`

### B. Add Environment Variables in Vercel Dashboard
Go to **Settings → Environment Variables**:

```
VITE_API_URL = https://nexus-backend-xxxx.onrender.com
```

### C. Vercel will auto-deploy on every `git push`

---

## Step 3 — Update config.js with your Render URL

Edit `frontend/config.js` — replace the fallback URL:
```js
"https://nexus-backend.onrender.com"  // → your actual Render URL
```

Then push:
```bash
git add .
git commit -m "chore: set Render backend URL"
git push origin main
```

---

## URLs After Deployment

| Page | URL |
|---|---|
| **Pricing** | `https://your-project.vercel.app/pricing` |
| **AI Sandbox** | `https://your-project.vercel.app/` |
| **Admin Dashboard** | `https://your-project.vercel.app/admin` |
| **API Docs** | `https://nexus-backend-xxxx.onrender.com/docs` |
| **Health Check** | `https://nexus-backend-xxxx.onrender.com/health` |

---

## Admin Login
```
Username: nexus
Password: nexus2026
```

---

## Subscription Plans
| Plan | Price | Credits |
|---|---|---|
| STARTER | $9/mo | 90 cr |
| PRO | $29/mo | 150 cr |
| ENTERPRISE | $99/mo | 600 cr |

1 Credit = $0.10 · Top-up packs: $5 / $10 / $25 / $50
