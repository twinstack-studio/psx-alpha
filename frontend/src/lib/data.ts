import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { cache } from "react";

import type { CompanyDetail, Dashboard } from "./types";

/**
 * The analysis bundle is written by the Python pipeline into `public/data`.
 * Reading it from the filesystem inside server components lets every page be
 * statically generated, so the dashboard loads instantly and works with no
 * backend running. Point `NEXT_PUBLIC_API_URL` at the FastAPI service instead
 * if you want live data.
 */
const DATA_DIR = path.join(process.cwd(), "public", "data");

export const getDashboard = cache(async (): Promise<Dashboard> => {
  const raw = await readFile(path.join(DATA_DIR, "dashboard.json"), "utf-8");
  return JSON.parse(raw) as Dashboard;
});

export const getCompany = cache(async (ticker: string): Promise<CompanyDetail | null> => {
  try {
    const raw = await readFile(
      path.join(DATA_DIR, "companies", `${ticker.toUpperCase()}.json`),
      "utf-8",
    );
    return JSON.parse(raw) as CompanyDetail;
  } catch {
    return null;
  }
});

export const listTickers = cache(async (): Promise<string[]> => {
  try {
    const files = await readdir(path.join(DATA_DIR, "companies"));
    return files.filter((f) => f.endsWith(".json")).map((f) => f.replace(/\.json$/, ""));
  } catch {
    return [];
  }
});
