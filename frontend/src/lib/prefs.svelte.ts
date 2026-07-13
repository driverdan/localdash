// localStorage-backed per-feature preference blobs (one JSON object per key).
// Loading is tolerant by design: a missing key, invalid JSON, a non-object value,
// or a wrong-typed field can never break page load — callers validate field by
// field with the as* helpers and fall back to that field's default. Storage
// write failures (quota, private mode) are swallowed; the app then runs on
// in-memory state only.
import { flushSync } from "svelte";

export function loadPrefs(key: string): Record<string, unknown> | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)
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
export const asString = (v: unknown): string | null => (typeof v === "string" ? v : null);
export const asBool = (v: unknown): boolean | null => (typeof v === "boolean" ? v : null);
export const asNumber = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;
export const asStringArray = (v: unknown): string[] | null =>
  Array.isArray(v) && v.every((x) => typeof x === "string") ? (v as string[]) : null;

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
export function persistPrefs(key: string, snapshot: () => Record<string, unknown>): PrefsPersister {
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
