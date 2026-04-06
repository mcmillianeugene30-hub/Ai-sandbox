# ⬡ Project Nexus — Autonomous AI Operating System v10.3 'Pure Encore'

> **The world's first industrial-grade self-evolving AI operating system, powered EXCLUSIVELY by Encore Cloud.** A unified, globally distributed platform for agents, RAG, and multi-provider AI.

[![Encore](https://img.shields.io/badge/Infrastructure-Encore_Cloud-625df5?logo=encore)](https://encore.dev)

---

## 🏗️ Single-Cloud Architecture (Pure Encore)

Project Nexus is now fully consolidated on **Encore Cloud**, eliminating the need for Render or Vercel.

| Component | Technology | Managed By |
| :--- | :--- | :--- |
| **Gateway** | Encore.ts | Encore Asset Engine |
| **Auth/Users** | Encore.ts | Encore Service Engine |
| **Database** | PostgreSQL | Encore SQL Primitives |
| **AI Engine** | Python (FastAPI) | Encore Container Service |
| **Dashboard** | HTML/JS/Monaco | Encore Static Hosting |

---

## 🚀 Deployment (One-Click)

1. **Install Encore CLI**: `curl -L https://encore.dev/install.sh | sh`
2. **Link & Deploy**:
   ```bash
   encore app link
   git push encore main
   ```
3. **Set Secrets**: 
   All keys (`GROQ_API_KEY`, `STRIPE_SECRET_KEY`, etc.) are managed in the **Encore Dashboard**.

---

## 📁 Project Structure
```text
.
├── ai_engine/          # Python AI Engine (Inference, RAG, 12 Agents)
├── gateway/            # Encore Gateway (Routing & Static Dashboard)
├── users/              # Encore User Service (Auth & Postgres)
├── static/             # Unified Control Center (Frontend)
└── encore.app          # Unified Cloud Blueprint
```

**One Cloud. One Command. One Empire.** 🚀✨
