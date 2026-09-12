/**
 * Copies the analysis bundle produced by the Python pipeline into
 * `public/data`, which is what the dashboard pages read at build time.
 *
 *   npm run sync-data
 */
import { cp, mkdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const source = path.resolve(here, "..", "..", "backend", "data", "exports");
const target = path.resolve(here, "..", "public", "data");

try {
  await stat(source);
} catch {
  console.error(`No exports at ${source}`);
  console.error("Run `python -m scripts.run_pipeline` in backend/ first.");
  process.exit(1);
}

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });
console.log(`Synced analysis bundle -> ${path.relative(process.cwd(), target)}`);
