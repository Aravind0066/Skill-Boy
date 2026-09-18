import "dotenv/config";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import pg from "pg";

const { Client } = pg;
const databaseUrl = process.env.DATABASE_URL;

if (!databaseUrl) {
    console.error("DATABASE_URL is required to run migrations.");
    process.exit(1);
}

const client = new Client({
    connectionString: databaseUrl,
    ssl: process.env.DATABASE_SSL === "false"
        ? false
        : { rejectUnauthorized: false },
});

try {
    const schemaPath = fileURLToPath(new URL("./supabase_schema.sql", import.meta.url));
    const schema = await fs.readFile(schemaPath, "utf8");

    await client.connect();
    await client.query("BEGIN");
    await client.query(schema);
    await client.query("COMMIT");
    console.log("Database migration completed successfully.");
} catch (error) {
    try {
        await client.query("ROLLBACK");
    } catch {
        // Ignore rollback errors when the connection was never established.
    }

    console.error("Database migration failed:", error.message);
    process.exitCode = 1;
} finally {
    await client.end().catch(() => {});
}