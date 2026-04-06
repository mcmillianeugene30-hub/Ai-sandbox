import { api } from "encore.dev/api";

// Serve static frontend
// In 2026, Encore uses the api.static primitive
export const assets = api.static({
    expose: true,
    path: "/!path",
    dir: "../static",
    notFound: "../static/index.html"
});

// Gateway logic
export const health = api({}, async (): Promise<{ status: string }> => {
    return { status: "Encore Gateway Operational" };
});
