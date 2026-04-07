import { api } from "encore.dev/api";
import { UserDB } from "./db";
import { secret } from "encore.dev/config";
import * as jwt from "jsonwebtoken";
import * as bcrypt from "bcryptjs";

const SecretKey = secret("SecretKey");
const GithubClientID = secret("GithubClientID");
const GoogleClientID = secret("GoogleClientID");

// ─── TYPES ───────────────────────────────────────────────────────────────────
interface RegisterRequest { username: string; password:  string; plan:      string; }
interface LoginRequest    { username: string; password:  string; }

// ─── AUTH ────────────────────────────────────────────────────────────────────

export const register = api(
    { method: "POST", path: "/api/v1/auth/register", expose: true },
    async (req: RegisterRequest): Promise<{ status: string }> => {
        const hash = await bcrypt.hash(req.password, 10);
        await UserDB.exec`
            INSERT INTO users (username, password_hash, plan_type, credits)
            VALUES (${req.username}, ${hash}, ${req.plan}, 100)
        `;
        return { status: "success" };
    }
);

export const login = api(
    { method: "POST", path: "/api/v1/auth/login", expose: true },
    async (req: LoginRequest): Promise<any> => {
        const user = await UserDB.queryRow`
            SELECT id, username, password_hash, plan_type, is_admin FROM users
            WHERE username = ${req.username}
        `;
        if (!user || !(await bcrypt.compare(req.password, user.password_hash))) {
            throw new Error("Invalid credentials");
        }
        const token = jwt.sign(
            { sub: user.username, id: user.id, is_admin: user.is_admin },
            SecretKey(),
            { expiresIn: '10h' }
        );
        return { access_token: token, token_type: "bearer" };
    }
);

export const getMe = api(
    { method: "GET", path: "/api/v1/user/me", expose: true },
    async (): Promise<any> => {
        return { username: "nexus_admin", credits: 9999, is_admin: true, plan: "ENTERPRISE" };
    }
);

// ─── SOCIAL LOGIN ────────────────────────────────────────────────────────────

export const githubLogin = api(
    { method: "GET", path: "/api/v1/auth/github", expose: true },
    async (): Promise<{ url: string }> => {
        return { url: `https://github.com/login/oauth/authorize?client_id=${GithubClientID()}&scope=user:email` };
    }
);

export const googleLogin = api(
    { method: "GET", path: "/api/v1/auth/google", expose: true },
    async (): Promise<{ url: string }> => {
        return { url: `https://accounts.google.com/o/oauth2/v2/auth?client_id=${GoogleClientID()}&response_type=code&scope=openid%20email` };
    }
);

// ─── BILLING & STRIPE ────────────────────────────────────────────────────────

export const stripeWebhook = api.raw(
    { method: "POST", path: "/api/v1/billing/webhook", expose: true },
    async (req, resp) => {
        // Stripe webhook logic here
        resp.statusCode = 200;
        resp.end(JSON.stringify({ status: "received" }));
    }
);

export const listPlans = api(
    { method: "GET", path: "/api/v1/billing/plans", expose: true },
    async (): Promise<any> => {
        return {
            "STARTER":   { "price": 9,  "credits": 90,  "models": ["llama-3.1-8b-instant"] },
            "PRO":       { "price": 29, "credits": 350, "models": ["*"] },
            "ENTERPRISE": { "price": 49, "credits": 600, "models": ["*"] }
        };
    }
);

// ─── ADMIN ───────────────────────────────────────────────────────────────────

export const getAdminStats = api(
    { method: "GET", path: "/api/v1/admin/stats", expose: true },
    async (): Promise<any> => {
        return {
            total_users: 1,
            arr_estimate: 588,
            total_spend_usd: 0.42,
            plan_breakdown: [{ plan: "ENTERPRISE", users: 1, mrr: 49 }],
            recent_logs: [],
            models: []
        };
    }
);
