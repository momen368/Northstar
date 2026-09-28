import { cp, mkdir, readdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const output = join(root, "dist");
const apiBaseUrl = (process.env.NORTHSTAR_API_BASE_URL ?? "").trim().replace(/\/+$/, "");
let parsedApiBaseUrl;

try {
  if (apiBaseUrl) parsedApiBaseUrl = new URL(apiBaseUrl);
} catch {
  throw new Error("NORTHSTAR_API_BASE_URL must be an absolute HTTP(S) URL.");
}
if (apiBaseUrl && !["http:", "https:"].includes(parsedApiBaseUrl.protocol)) {
  throw new Error("NORTHSTAR_API_BASE_URL must be an absolute HTTP(S) URL.");
}
if (process.env.VERCEL === "1" && !apiBaseUrl) {
  throw new Error("Set NORTHSTAR_API_BASE_URL in the Vercel project environment variables.");
}
if (process.env.VERCEL === "1" && (parsedApiBaseUrl.protocol !== "https:" || ["localhost", "127.0.0.1", "::1"].includes(parsedApiBaseUrl.hostname))) {
  throw new Error("Vercel deployments require a public HTTPS backend URL, not localhost.");
}

await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
for (const entry of await readdir(root, { withFileTypes: true })) {
  if (["dist", "node_modules", "package.json", "package-lock.json", "build.mjs"].includes(entry.name)) continue;
  await cp(join(root, entry.name), join(output, entry.name), { recursive: true });
}

const configPath = join(output, "assets", "js", "deployment-config.js");
await mkdir(dirname(configPath), { recursive: true });
await writeFile(configPath, `export const API_BASE_URL = ${JSON.stringify(apiBaseUrl)};\n`, "utf8");
console.log(`Built static frontend in ${output}${apiBaseUrl ? ` (API: ${apiBaseUrl})` : " (relative API URLs)"}`);
