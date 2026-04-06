import { SQLDatabase } from "encore.dev/storage";

// Define the User database
export const UserDB = new SQLDatabase("users", {
    migrations: "./migrations",
});
