"use client";

/**
 * A watchlist kept in the browser.
 *
 * The dashboard is statically generated and has no user accounts, so the list
 * lives in localStorage. Every component that reads it subscribes to the same
 * store through `useSyncExternalStore`, which means a star toggled in the
 * screener updates the sidebar count and the compare tray in the same frame —
 * and a change made in another tab arrives through the `storage` event.
 */

import { useCallback, useSyncExternalStore } from "react";

const KEY = "psx-alpha:watchlist";

type Listener = () => void;
const listeners = new Set<Listener>();

/** Cached so `getSnapshot` returns a stable reference between real changes. */
let snapshot: string[] = [];
let hydrated = false;

function read(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((t): t is string => typeof t === "string") : [];
  } catch {
    // Private mode, blocked site data, or corrupt JSON: an empty watchlist is
    // the right answer in all three cases.
    return [];
  }
}

function write(next: string[]) {
  snapshot = next;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* quota or blocked storage: the in-memory list still works for this tab */
  }
  listeners.forEach((l) => l());
}

function subscribe(l: Listener) {
  listeners.add(l);
  const onStorage = (e: StorageEvent) => {
    if (e.key !== KEY) return;
    snapshot = read();
    listeners.forEach((x) => x());
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(l);
    window.removeEventListener("storage", onStorage);
  };
}

function getSnapshot(): string[] {
  if (!hydrated) {
    snapshot = read();
    hydrated = true;
  }
  return snapshot;
}

/** The server has no localStorage, so it renders an empty list. */
const EMPTY: string[] = [];
const getServerSnapshot = () => EMPTY;

export function useWatchlist() {
  const tickers = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const toggle = useCallback((ticker: string) => {
    const cur = getSnapshot();
    write(cur.includes(ticker) ? cur.filter((t) => t !== ticker) : [...cur, ticker]);
  }, []);

  const clear = useCallback(() => write([]), []);

  const has = useCallback((ticker: string) => tickers.includes(ticker), [tickers]);

  return { tickers, toggle, clear, has, count: tickers.length };
}
