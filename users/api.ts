import { api } from "encore.dev/api";
import { UserDB } from "./db";

interface RegisterRequest {
    username: string;
    password:  string;
    plan:      string;
}

export const register = api(
    { method: "POST", path: "/auth/register", expose: true },
    async (req: RegisterRequest): Promise<{ status: string }> => {
        // In real prod: hash password, validate plan
        await UserDB.exec`
            INSERT INTO users (username, password_hash, plan_type, credits)
            VALUES (${req.username}, ${req.password}, ${req.plan}, 100)
        `;
        return { status: "User registered in Encore DB" };
    }
);

export const getMe = api(
    { method: "GET", path: "/user/me", expose: true },
    async (): Promise<any> => {
        // Mock session logic for now
        return { username: "nexus_encore", credits: 100, is_admin: true };
    }
);
