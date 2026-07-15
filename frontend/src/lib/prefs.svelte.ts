// localStorage-backed per-feature preference blobs (one JSON object per key).
// Loading is tolerant by design: a missing key, invalid JSON, a non-object value,
// or a wrong-typed field can never break page load — callers validate field by
// field with the as* helpers and fall back to that field's default. Storage
// write failures (quota, private mode) are swallowed; the app then runs on
// in-memory state only.
import { flushSync } from "svelte";

/**
 * Reserved namespace for every key the frontend persists for a browser. It
 * spans keys this module never writes — `localdash.theme` (owned by
 * lib/theme.svelte, which must apply before first paint) and namespaced view
 * state like `localdash.map.view` — so `listPrefs` can enumerate a browser's
 * stored preferences without being told the key names. Any new persisted
 * preference key belongs under it.
 */
export const PREFS_PREFIX = "localdash.";

export interface StoredPref {
  key: string;
  /** The value exactly as stored; callers decide how (or whether) to parse it. */
  raw: string;
}

/**
 * The namespace's keys currently in storage, sorted for a stable render order.
 * Only stored keys are reported — a key that was never written is absent, not
 * empty, and that difference matters: an absent `localdash.map` means every
 * category is on (including ones added later), where a present one is an
 * allowlist.
 */
export function listPrefs(): StoredPref[] {
  try {
    const out: StoredPref[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key === null || !key.startsWith(PREFS_PREFIX)) continue;
      const raw = localStorage.getItem(key);
      if (raw !== null) out.push({ key, raw });
    }
    return out.sort((a, b) => a.key.localeCompare(b.key));
  } catch {
    return []; // storage unavailable — same swallow as the other read paths
  }
}

export function loadPrefs(key: string): Record<string, unknown> | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return parsed !== null &&
      typeof parsed === "object" &&
      !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export function savePrefs(key: string, obj: Record<string, unknown>): void {
  try {
    localStorage.setItem(key, JSON.stringify(obj));
  } catch {
    /* storage unavailable or full — run without persistence */
  }
}

export function removePrefs(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

// Per-field validators: null means "not usable, keep the default".
export const asString = (v: unknown): string | null =>
  typeof v === "string" ? v : null;
export const asBool = (v: unknown): boolean | null =>
  typeof v === "boolean" ? v : null;
export const asNumber = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;
export const asStringArray = (v: unknown): string[] | null =>
  Array.isArray(v) && v.every((x) => typeof x === "string")
    ? (v as string[])
    : null;

export interface PrefsPersister {
  /**
   * Run `mutate` (restoring persisted state to its defaults) without the change
   * being re-saved, then delete the stored key — so the browser behaves as if it
   * had no saved preferences until the next real change.
   */
  resetTo(mutate: () => void): void;
}

/**
 * Save `snapshot()` under `key` whenever any reactive value it reads changes.
 * The first run only registers dependencies — a visitor who never changes a
 * preference never gets a key written (key-presence is what switches saved
 * source/category selections into allowlist mode).
 */
export function persistPrefs(
  key: string,
  snapshot: () => Record<string, unknown>,
): PrefsPersister {
  let mode: "first" | "on" | "suppressed" = "first";
  $effect.root(() => {
    $effect(() => {
      const snap = snapshot(); // read (and track) even when not saving
      if (mode === "first") {
        mode = "on";
      } else if (mode === "on") {
        savePrefs(key, snap);
      }
    });
  });
  return {
    resetTo(mutate: () => void) {
      mode = "suppressed";
      try {
        mutate();
        flushSync(); // run the effect now, while saves are suppressed
      } finally {
        mode = "on";
      }
      removePrefs(key);
    },
  };
}
