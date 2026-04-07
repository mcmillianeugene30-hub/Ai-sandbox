import { api } from "encore.dev/api";
import { UserDB } from "../users/db";

// ─── STATIC FRONTEND ─────────────────────────────────────────────────────────
export const assets = api.static({
    expose: true,
    path: "/!path",
    dir: "../static",
    notFound: "../static/index.html"
});

// ─── WORKSPACES ──────────────────────────────────────────────────────────────

export const listWorkspaces = api(
    { method: "GET", path: "/api/v1/workspaces", expose: true },
    async (): Promise<any[]> => {
        const rows = UserDB.query`SELECT id, name, created_at FROM workspaces`;
        const workspaces: any[] = [];
        for await (const row of rows) { workspaces.push(row); }
        return workspaces;
    }
);

export const createWorkspace = api(
    { method: "POST", path: "/api/v1/workspaces", expose: true },
    async (req: { name: string }): Promise<any> => {
        await UserDB.exec`INSERT INTO workspaces (user_id, name) VALUES (1, ${req.name})`;
        return { status: "created" };
    }
);

export const getWorkspace = api(
    { method: "GET", path: "/api/v1/workspaces/:id", expose: true },
    async ({ id }: { id: number }): Promise<any> => {
        const row = await UserDB.queryRow`SELECT id, name, config FROM workspaces WHERE id = ${id}`;
        if (!row) throw new Error("Not found");
        return row;
    }
);

export const updateWorkspace = api(
    { method: "PUT", path: "/api/v1/workspaces/:id", expose: true },
    async ({ id, config }: { id: number, config: string }): Promise<any> => {
        await UserDB.exec`UPDATE workspaces SET config = ${config} WHERE id = ${id}`;
        return { status: "updated" };
    }
);

// ─── AI ENGINE PROXY ─────────────────────────────────────────────────────────
const AI_ENDPOINTS = [
    "models", "chat", "kb", "nexus", "swarm", 
    "singularity", "autodeploy", "orchestrator", "judge"
];

export const aiProxy = api.raw(
    { method: "*", path: "/api/v1/:endpoint/!rest", expose: true },
    async (req, resp) => {
        const { endpoint } = req.params;
        if (!AI_ENDPOINTS.includes(endpoint)) {
            resp.statusCode = 404;
            resp.end(JSON.stringify({ error: "Endpoint not found in AI proxy" }));
            return;
        }

        const targetUrl = `http://ai-engine:8000/api/v1/${endpoint}/${req.params.rest}${req.url.search}`;
        try {
            const res = await fetch(targetUrl, {
                method: req.method,
                headers: req.headers,
                body: req.body
            });
            res.headers.forEach((v, k) => resp.setHeader(k, v));
            resp.statusCode = res.status;
            if (res.body) {
                const reader = res.body.getReader();
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    resp.write(value);
                }
            }
            resp.end();
        } catch (err) {
            resp.statusCode = 502;
            resp.end(JSON.stringify({ error: "AI Engine Unreachable" }));
        }
    }
);

export const health = api({ method: "GET", path: "/health", expose: true }, async () => ({ status: "ok" }));
