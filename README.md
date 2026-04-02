# ⬡ Project Nexus — Autonomous AI Operating System v8.0

> **The world's most advanced self-evolving AI sandbox.** From a simple multi-provider playground to a full autonomous AI operating system — built, versioned, and deployed end-to-end.

[![Deploy](https://img.shields.io/badge/Frontend-Vercel-black?logo=vercel)](https://vercel.com)
[![Backend](https://img.shields.io/badge/Backend-Render-46E3B7?logo=render)](https://render.com)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 🌌 What We Built

Starting from a blank sandbox, we evolved this project through **8 major versions** into a production-ready, self-improving, commercially monetized AI operating system.

---

## 🏗️ Evolution Timeline

| Version | Milestone | Key Features |
|---|---|---|
| **v1.0** | AI Sandbox | Multi-provider chat (Gemini, Groq, OpenRouter), Python & JS SDKs |
| **v2.0** | Developer Platform | SSE streaming, Ollama local AI, usage analytics, React/Flutter code export |
| **v3.0** | Production Ready | RAG with ChromaDB, side-by-side model evaluation, compare mode, KB uploads |
| **v4.0** | Agentic Power | LLM-as-a-Judge, Fine-Tuning Exporter, Visual Agent Orchestrator |
| **v5.0** | Full-Stack Builder | AppArchitect Agent, DevOps Agent, multi-file code generation, Docker configs |
| **v6.0** | Enterprise | Admin Auth (Argon2 + JWT), Billing Dashboard, usage tracking in USD |
| **v7.0** | Revenue Platform | Subscription plans, credit system, no free tier, top-up packs, model gating |
| **v8.0** | Frontier OS | Auto-Deploy, Autonomous Model Discovery, Swarm Intelligence, Self-Evolution |

---

## 🧠 Core Capabilities

### 🔬 AI Sandbox Playground
- Multi-provider chat completions: **Groq**, **Gemini**, **OpenRouter**, **Ollama**
- Monaco code editor with live execution
- Real-time SSE streaming
- RAG toggle (ChromaDB knowledge base)
- Side-by-side model comparison
- React Hook & Flutter code export

### 🤖 Nexus AI-OS — Autonomous Agents
| Agent | Role |
|---|---|
| **NexusKernel** | Central routing engine with async Hive Polling |
| **AppArchitectAgent** | Designs 2026 full-stack app structure and tech stack |
| **DevOpsAgent** | Generates Dockerfiles, docker-compose, GitHub Actions |
| **PlannerAgent** | Decomposes complex goals into parallel sub-tasks |
| **ResearcherAgent** | RAG-powered research with MemoryBank recall |
| **CoderAgent** | Multi-file code generation with few-shot learning |
| **ReviewerAgent** | Autonomous code auditing with JSON verdicts |
| **HiveAggregator** | Synthesizes consensus from multi-model parallel polls |
| **SelfMonitorAgent** | Analyses usage logs for performance bottlenecks |
| **RecursiveCoderAgent** | Rewrites its own kernel source code autonomously |
| **AutoDeployAgent** | Trigger → Poll → Health Check → Auto-Rollback on Render |
| **AutonomousModelResearcher** | Scans Groq/OpenRouter/Gemini for new models, evaluates & registers them |

### 🐝 Swarm Intelligence
- **SwarmBus** — SQLite message broker (Redis-compatible interface)
- **SwarmNode** — Independent agent with heartbeat, task queue, and result publishing
- **SwarmOrchestrator** — AI-powered goal decomposition → parallel execution → consensus synthesis
- Up to 8 nodes working simultaneously on a single goal

### 🧬 Singularity — Self-Evolution
1. **Self-Monitor** detects errors/bottlenecks from `usage_logs`
2. **Recursive Coder** rewrites `core/kernel.py` with optimized routing
3. **Hot-Swap Engine** reloads the new kernel into memory without restart

### 💰 Monetization Engine
| Plan | Price | Credits | Models |
|---|---|---|---|
| **STARTER** | $9/mo | 90 cr | Llama 8B, Gemini Flash |
| **PRO** | $29/mo | 150 cr | Llama 70B, Gemini Pro, Mistral |
| **ENTERPRISE** | $99/mo | 600 cr | ALL models incl. GPT-4o, Claude |

- **1 Credit = $0.10** — every agent step, deploy, and token deducted automatically
- **Credit Ledger** — atomic, tamper-proof transaction log
- **Top-up Packs**: Micro $5 / Builder $10 / Power $25 / Studio $50
- **Fine-tuning Export** — star good interactions → download JSONL

---

## 📁 Project Structure

```
Ai-sandbox/
├── backend/
│   ├── main.py              # FastAPI — 35 endpoints (auth, billing, chat, RAG,
│   │                        #   swarm, singularity, autodeploy, model discovery)
│   ├── providers.py         # Gemini, Groq, OpenRouter, Ollama adapters
│   ├── rag_manager.py       # ChromaDB vector store + PDF/text ingestion
│   ├── orchestrator.py      # LangGraph-style agent chain runner
│   └── requirements.txt     # All Python dependencies
│
├── frontend/
│   ├── dashboard.html       # ✅ UNIFIED single-page dashboard (10 tabs, 1775 lines)
│   ├── pricing.html         # Revenue Intelligence pricing page
│   ├── config.js            # API base URL (reads VITE_API_URL env var)
│   ├── index.html           # Legacy sandbox (redirects to dashboard)
│   ├── script.js            # Sandbox JS logic
│   └── style.css            # Dark theme styles
│
├── nexus-ai-os/
│   ├── agents/
│   │   ├── architect.py         # Full-stack app design
│   │   ├── auto_deploy.py       # Render CI/CD automation
│   │   ├── coder.py             # Multi-file self-healing coder
│   │   ├── devops.py            # Docker + GitHub Actions generation
│   │   ├── hive_aggregator.py   # Multi-model consensus synthesis
│   │   ├── model_researcher.py  # Autonomous model discovery
│   │   ├── planner.py           # Goal decomposition
│   │   ├── researcher.py        # RAG + MemoryBank research
│   │   ├── reviewer.py          # Code audit + scoring
│   │   └── self_monitor.py      # Performance analysis + kernel rewriting
│   ├── core/
│   │   ├── kernel.py            # Async NexusKernel + Hive Polling
│   │   ├── memory_bank.py       # ChromaDB persistent memory
│   │   ├── hot_swap.py          # Dynamic module reloader
│   │   └── swarm.py             # SwarmBus + SwarmNode + SwarmOrchestrator
│   └── tools/
│       ├── fs_tool.py           # File system operations for agents
│       ├── shell.py             # Sandboxed shell execution
│       └── python_exec.py       # Sandboxed Python execution
│
├── sdks/
│   ├── python/aisandbox.py      # Python SDK with streaming support
│   └── javascript/aisandbox.js  # JS SDK with async iterator streaming
│
├── Dockerfile                   # Multi-stage production Docker image
├── docker-compose.yml           # Backend + Nginx frontend services
├── render.yaml                  # Render auto-deploy blueprint
├── vercel.json                  # Vercel routing config
├── nginx.conf                   # SSE-compatible reverse proxy
├── build.sh                     # Render build entry point
├── DEPLOY.md                    # Full Vercel + Render deployment guide
├── .env.example                 # All required environment variables
└── README.md                    # This file
```

---

## 🚀 Deployment

**Frontend → Vercel** | **Backend → Render**

### Quick Start

```bash
# 1. Clone
git clone https://github.com/mcmillianeugene30-hub/Ai-sandbox.git
cd Ai-sandbox

# 2. Set environment variables
cp .env.example backend/.env
# Edit backend/.env with your API keys

# 3. Run locally with Docker
docker-compose up --build

# 4. Access
# Frontend: http://localhost:8080/dashboard.html
# Backend API: http://localhost:8000/docs
# Pricing: http://localhost:8080/pricing.html
```

### Production Deploy

| Platform | Config | What gets deployed |
|---|---|---|
| **Render** | `render.yaml` | FastAPI backend — 35 API routes |
| **Vercel** | `vercel.json` | Unified dashboard + pricing page |

See **[DEPLOY.md](DEPLOY.md)** for the full step-by-step guide.

---

## 🌐 API Reference — All 35 Endpoints

### Auth
| Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register with plan (STARTER/PRO/ENTERPRISE) |
| `POST` | `/api/v1/auth/login` | Get JWT access token |
| `GET` | `/api/v1/user/me` | Get current user profile + credit balance |

### AI Sandbox
| Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/chat/completions` | Plan-gated, credit-deducting chat completions |
| `GET` | `/api/v1/models` | List all available models by provider |
| `POST` | `/api/v1/kb/upload` | Upload PDF/text to RAG knowledge base |
| `GET` | `/api/v1/analytics` | Per-user usage analytics by provider |

### Billing
| Method | Route | Description |
|---|---|---|
| `GET` | `/api/v1/billing/plans` | List subscription plans |
| `GET` | `/api/v1/billing/packs` | List top-up credit packs |
| `POST` | `/api/v1/billing/topup` | Add credits via top-up pack |
| `POST` | `/api/v1/billing/upgrade` | Upgrade subscription plan |
| `GET` | `/api/v1/billing/ledger` | Full credit transaction history |

### Admin
| Method | Route | Description |
|---|---|---|
| `GET` | `/api/v1/admin/stats` | KPIs: users, MRR, ARR, API cost, model usage |
| `GET` | `/api/v1/admin/users` | List all users with plans and balances |
| `POST` | `/api/v1/admin/users/{id}/grant` | Grant bonus credits to a user |
| `POST` | `/api/v1/admin/users/{id}/set-plan` | Change a user's subscription plan |
| `POST` | `/api/v1/admin/star/{log_id}` | Star a log for fine-tuning export |
| `GET` | `/api/v1/admin/export` | Download starred logs as JSONL |

### Nexus AI-OS
| Method | Route | Description |
|---|---|---|
| `GET` | `/api/v1/nexus/app-build` | SSE: Full-stack app builder (PRO/ENTERPRISE) |

### Swarm Intelligence
| Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/swarm/run` | Run multi-node swarm on a goal |
| `GET` | `/api/v1/swarm/stream` | SSE: Real-time swarm execution stream |
| `GET` | `/api/v1/swarm/nodes` | List all live swarm nodes |

### Model Discovery
| Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/models/discover` | Scan all providers for new models + auto-register |
| `GET` | `/api/v1/models/registry` | View full discovered model registry |

### Auto-Deploy
| Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/autodeploy/trigger` | Trigger → Poll → Health Check → Rollback |
| `GET` | `/api/v1/autodeploy/status` | Get latest Render deploy statuses |

### Singularity
| Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/singularity/evolve` | Trigger self-evolution cycle |
| `GET` | `/api/v1/singularity/status` | Error rate, kernel modified time |

### System
| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Health check (used by Render + AutoDeployAgent) |
| `GET` | `/` | API root + version info |
| `GET` | `/docs` | Auto-generated Swagger UI |

---

## 🔑 Environment Variables

### Render (Backend)
```env
GROQ_API_KEY          # Groq LLM API
GEMINI_API_KEY         # Google Gemini API
OPENROUTER_API_KEY     # OpenRouter (GPT-4o, Claude, free models)
SECRET_KEY             # JWT signing secret — change in production!
FRONTEND_URL           # Your Vercel URL (for CORS)
RENDER_SERVICE_URL     # Your Render backend URL (for health checks)
RENDER_API_KEY         # Optional: enables Auto-Deploy pipeline
RENDER_SERVICE_ID      # Optional: paired with RENDER_API_KEY
```

### Vercel (Frontend)
```env
VITE_API_URL           # Your Render backend URL
```

Generate a secure SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🖥️ Unified Dashboard — 10 Tabs

Access at: `https://your-project.vercel.app/dashboard`  
Admin login: `nexus` / `nexus2026`

| Tab | Feature |
|---|---|
| 🔬 **SANDBOX** | Monaco editor, provider/model select, stream/RAG/compare mode |
| 📊 **OVERVIEW** | Live KPIs — Users, MRR, ARR, API cost, plan breakdown |
| 👤 **USERS** | User management — grant credits, change plans |
| 📋 **LOGS** | Audit trail — star interactions, export JSONL for fine-tuning |
| 💳 **BILLING** | Plan config, top-up packs, credit economy |
| 🐝 **SWARM** | Multi-node swarm execution with live SSE log |
| 🔍 **MODELS** | Autonomous provider scanning + model registry |
| 🚀 **DEPLOY** | One-click Render deploy with health check + rollback |
| 🧬 **SINGULARITY** | Self-evolution — monitor → propose → rewrite → hot-swap |
| ⚡ **TERMINAL** | Full-stack app builder terminal with live streaming |

---

## 🛠️ SDK Usage

### Python SDK
```python
from sdks.python.aisandbox import AISandboxClient

client = AISandboxClient(base_url="https://nexus-backend-xxxx.onrender.com")
response = client.chat.completions(
    provider="groq",
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response)
```

### JavaScript SDK
```javascript
import AISandboxClient from './sdks/javascript/aisandbox.js';

const client = new AISandboxClient('https://nexus-backend-xxxx.onrender.com');
const stream = await client.chat.completions('groq', 'llama-3.3-70b-versatile', messages, { stream: true });

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0].delta?.content || '');
}
```

---

## 📊 Revenue Projections

| Stage | Paid Users | MRR | ARR | Margin |
|---|---|---|---|---|
| 🌱 Early Traction | 100 | $2,280 | $27,360 | ~92% |
| 🚀 Growth | 500 | $14,580 | $174,960 | ~91% |
| 🏆 Scale | 2,000 | $60,300 | $723,600 | ~90% |

> Free-API stack (Groq, Gemini Flash, OpenRouter free tier) costs under $100/mo to serve 500 users.

---

## 🗺️ Architecture Overview

```
User → Vercel (dashboard.html)
          │
          │ HTTPS/SSE
          ▼
   Render (FastAPI backend)
          │
   ┌──────┴──────────────────────────────┐
   │                                     │
   ▼                                     ▼
providers.py                    nexus-ai-os/
(Groq/Gemini/OpenRouter/Ollama)   ├── NexusKernel (async)
          │                       ├── Hive Polling
          │                       ├── SwarmBus (SQLite)
          ▼                       ├── MemoryBank (ChromaDB)
rag_manager.py                    └── HotSwapEngine
(ChromaDB + embeddings)
          │
          ▼
   usage.db (SQLite)
   ├── users + credits
   ├── credit_ledger
   ├── usage_logs
   └── pricing_config
```

---

## 🏆 Achievements

- ✅ **8 major versions** shipped from scratch
- ✅ **35 API endpoints** — auth, billing, AI, agents, swarm, singularity
- ✅ **12 autonomous agents** working in concert
- ✅ **Self-evolving kernel** — the AI rewrites its own source code
- ✅ **Swarm intelligence** — up to 8 parallel nodes with consensus
- ✅ **Commercial platform** — subscriptions, credits, audit logs, JSONL export
- ✅ **Production deployed** — Render backend + Vercel frontend
- ✅ **Fully dockerized** with multi-stage Dockerfile and nginx
- ✅ **Zero-touch CI/CD** via AutoDeployAgent + Render API

---

## 🔮 What's Next

- [ ] Stripe webhook integration for real payment processing
- [ ] Redis SwarmBus for multi-server swarm scaling  
- [ ] Visual node editor (LiteGraph.js) for agent workflow design
- [ ] LLM-as-a-Judge evaluation leaderboard
- [ ] Scheduled self-evolution (cron-based kernel improvement)
- [ ] Multi-tenant project isolation per user

---

## 📄 License

MIT — Built with 🤖 by Project Nexus

---

*"We didn't just build an AI tool — we built an AI that builds, monitors, deploys, and improves itself."*
