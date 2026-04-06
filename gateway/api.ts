import { api } from "encore.dev/api";
import { UserDB } from "../users/db"; // Direct DB access across services is discouraged in real prod but allowed in monolith-style Encore

// Serve static frontend
export const assets = api.static({
    expose: true,
    path: "/!path",
    dir: "../static",
    notFound: "../static/index.html"
});

// ─── WORKSPACES ──────────────────────────────────────────────────────────────

export const listWorkspaces = api(
    { method: "GET", path: "/workspaces", expose: true },
    async (): Promise<any[]> => {
        const rows = UserDB.query`SELECT id, name, created_at FROM workspaces`;
        const workspaces: any[] = [];
        for await (const row of rows) {
            workspaces.push(row);
        }
        return workspaces;
    }
);

export const createWorkspace = api(
    { method: "POST", path: "/workspaces", expose: true },
    async (req: { name: string }): Promise<any> => {
        // In real prod: get user ID from auth
        await UserDB.exec`INSERT INTO workspaces (user_id, name) VALUES (1, ${req.name})`;
        return { status: "created" };
    }
);

export const getWorkspace = api(
    { method: "GET", path: "/workspaces/:id", expose: true },
    async ({ id }: { id: number }): Promise<any> => {
        const row = await UserDB.queryRow`SELECT id, name, config FROM workspaces WHERE id = ${id}`;
        if (!row) throw new Error("Not found");
        return row;
    }
);

export const updateWorkspace = api(
    { method: "PUT", path: "/workspaces/:id", expose: true },
    async ({ id, config }: { id: number, config: string }): Promise<any> => {
        await UserDB.exec`UPDATE workspaces SET config = ${config} WHERE id = ${id}`;
        return { status: "updated" };
    }
);

// ─── PROXY ───────────────────────────────────────────────────────────────────

export const legacyProxy = api.raw(
    { method: "*", path: "/v1/!path", expose: true },
    async (req, resp) => {
        const path = req.path.replace("/v1/", "");
        const targetUrl = `http://ai-engine:8000/api/v1/${path}${req.url.search}`;
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
    }
);

const AI_ENDPOINTS = ["models", "chat", "kb", "nexus", "swarm", "singularity", "autodeploy", "orchestrator", "judge"];

export const aiProxy = api.raw(
    { method: "*", path: "/:endpoint/!rest", expose: true },
    async (req, resp) => {
        const { endpoint } = req.params;
        if (!AI_ENDPOINTS.includes(endpoint)) {
            resp.statusCode = 404;
            resp.end("Not Found");
            return;
        }
        const targetUrl = `http://ai-engine:8000/api/v1/${endpoint}/${req.params.rest}${req.url.search}`;
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
    }
);

export const health = api({ method: "GET", path: "/health", expose: true }, async () => ({ status: "ok" }));
