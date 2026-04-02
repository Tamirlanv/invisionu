/**
 * localStorage draft persistence for candidate application forms.
 *
 * Each tab stores its own draft under a namespaced key like "invision:draft:personal".
 * Drafts are versioned — if the schema version changes, stale data is silently discarded.
 */

const PREFIX = "invision:draft:";
const SCHEMA_VERSION = 1;

interface Envelope<T> {
  v: number;
  ts: number;
  data: T;
}

function storageKey(section: string): string {
  return `${PREFIX}${section}`;
}

function isServer(): boolean {
  return typeof window === "undefined";
}

export function saveDraft<T>(section: string, data: T): boolean {
  if (isServer()) return false;
  try {
    const envelope: Envelope<T> = { v: SCHEMA_VERSION, ts: Date.now(), data };
    localStorage.setItem(storageKey(section), JSON.stringify(envelope));
    return true;
  } catch {
    return false;
  }
}

export function loadDraft<T>(section: string): T | null {
  if (isServer()) return null;
  try {
    const raw = localStorage.getItem(storageKey(section));
    if (!raw) return null;
    const envelope: Envelope<T> = JSON.parse(raw);
    if (!envelope || typeof envelope !== "object" || envelope.v !== SCHEMA_VERSION || !envelope.data) {
      return null;
    }
    return envelope.data;
  } catch {
    localStorage.removeItem(storageKey(section));
    return null;
  }
}

export function clearDraft(section: string): void {
  if (isServer()) return;
  try {
    localStorage.removeItem(storageKey(section));
  } catch {
    /* quota / security errors — ignore */
  }
}

export function clearAllDrafts(): void {
  if (isServer()) return;
  try {
    const keys = Object.keys(localStorage).filter((k) => k.startsWith(PREFIX));
    for (const k of keys) localStorage.removeItem(k);
  } catch {
    /* ignore */
  }
}
