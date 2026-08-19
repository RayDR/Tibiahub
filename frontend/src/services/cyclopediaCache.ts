/**
 * Cyclopedia client-side cache.
 *
 * Three layers:
 * 1. In-memory Map  — fast tab switching (10-min TTL, keyed by mode+filters)
 * 2. Per-tab sessionStorage snapshots — scroll/filter state per tab,
 *    survives navigating to a detail page and pressing Back.
 * 3. Server version checking — if /system/version returns a newer
 *    data_version than we last saw, client knowledge caches are invalidated
 *    so the next fetch retrieves fresh data.
 */

import { clearKnowledgeRequestCache } from './knowledgeRequestCache';

const TTL_MS = 10 * 60 * 1000;
const SNAPSHOT_TTL_MS = 30 * 60 * 1000;

// ── in-memory result cache ────────────────────────────────────────────────────

interface CacheEntry<T = unknown> {
  data: T;
  expiresAt: number;
  dataVersion?: string;
}

const _cache = new Map<string, CacheEntry>();

export function cacheGet<T>(key: string): T | null {
  const entry = _cache.get(key);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    _cache.delete(key);
    return null;
  }
  return entry.data as T;
}

export function cacheSet<T>(key: string, data: T, ttlMs = TTL_MS): void {
  _cache.set(key, {
    data,
    expiresAt: Date.now() + ttlMs,
    dataVersion: _knownDataVersion ?? undefined,
  });
}

export function cacheClear(prefix?: string): void {
  if (!prefix) {
    _cache.clear();
    return;
  }
  for (const key of _cache.keys()) {
    if (key.startsWith(prefix)) _cache.delete(key);
  }
}

export function buildCacheKey(params: {
  mode: string;
  search: string;
  category: string;
  sort: string;
  order: string;
  skip: number;
}): string {
  return `cyclopedia:${params.mode}:${params.skip}:${params.search}:${params.category}:${params.sort}:${params.order}`;
}

// ── server version tracking ───────────────────────────────────────────────────

const VERSION_STORAGE_KEY = 'cyclopedia_data_version';
let _knownDataVersion: string | null = null;

function _loadStoredVersion(): string | null {
  try { return sessionStorage.getItem(VERSION_STORAGE_KEY); } catch { return null; }
}

function _saveVersion(v: string): void {
  _knownDataVersion = v;
  try { sessionStorage.setItem(VERSION_STORAGE_KEY, v); } catch { /* ignore */ }
}

/**
 * Compare server data_version with local. If different, clear client knowledge
 * caches. Fire-and-forget — failure falls back to each cache's TTL.
 */
export async function checkAndInvalidateIfStale(): Promise<void> {
  if (!_knownDataVersion) _knownDataVersion = _loadStoredVersion();
  try {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), 5000);
    const res = await fetch('/api/v1/system/version', {
      cache: 'no-store',
      signal: controller.signal,
    });
    clearTimeout(tid);
    if (!res.ok) return;
    const json = (await res.json()) as { data_version?: string | null };
    const serverVersion = json?.data_version ?? null;
    if (!serverVersion) return;
    if (serverVersion !== _knownDataVersion) {
      _cache.clear();
      clearKnowledgeRequestCache();
      _saveVersion(serverVersion);
    }
  } catch { /* Version check failure is non-fatal */ }
}

// ── per-tab sessionStorage snapshots ─────────────────────────────────────────

const SNAPSHOT_PREFIX = 'cyclopedia_snap_';

export interface CyclopediaSnapshot {
  mode: string;
  searchTerm: string;
  selected: string;
  category: string;
  sort: string;
  order: string;
  scrollY: number;
  savedAt: number;
}

function _snapKey(tab: string): string {
  return `${SNAPSHOT_PREFIX}${tab}`;
}

export function saveSnapshot(snapshot: CyclopediaSnapshot): void {
  try {
    sessionStorage.setItem(_snapKey(snapshot.mode), JSON.stringify({ ...snapshot, savedAt: Date.now() }));
  } catch { /* ignore */ }
}

export function loadSnapshot(tab: string): CyclopediaSnapshot | null {
  try {
    const raw = sessionStorage.getItem(_snapKey(tab));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CyclopediaSnapshot;
    if (Date.now() - (parsed.savedAt || 0) > SNAPSHOT_TTL_MS) {
      sessionStorage.removeItem(_snapKey(tab));
      return null;
    }
    return parsed;
  } catch { return null; }
}

export function clearSnapshot(tab?: string): void {
  try {
    if (tab) {
      sessionStorage.removeItem(_snapKey(tab));
    } else {
      const keys: string[] = [];
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i);
        if (k?.startsWith(SNAPSHOT_PREFIX)) keys.push(k);
      }
      keys.forEach((k) => sessionStorage.removeItem(k));
    }
  } catch { /* ignore */ }
}