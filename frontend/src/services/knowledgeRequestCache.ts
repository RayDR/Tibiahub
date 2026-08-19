const DEFAULT_TTL_MS = 5 * 60 * 1000;

interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

const cache = new Map<string, CacheEntry<unknown>>();

function normalizeValue(value: unknown): string {
  if (value == null) return '';
  if (Array.isArray(value)) return value.map(normalizeValue).join(',');
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, nested]) => `${key}:${normalizeValue(nested)}`)
      .join('|');
  }
  return String(value);
}

export function knowledgeCacheKey(
  path: string,
  params?: Record<string, unknown>,
): string {
  const query = params
    ? Object.entries(params)
        .filter(([, value]) => value !== undefined && value !== null && value !== '')
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(normalizeValue(value))}`)
        .join('&')
    : '';

  return query ? `${path}?${query}` : path;
}

/**
 * Cache only successful public knowledge reads. Errors are never retained, so a
 * transient 404/500 cannot poison future navigation. Abort semantics remain in
 * the caller's loader on cache misses.
 */
export async function cachedKnowledgeRead<T>(
  key: string,
  loader: () => Promise<T>,
  ttlMs = DEFAULT_TTL_MS,
): Promise<T> {
  const existing = cache.get(key) as CacheEntry<T> | undefined;
  if (existing) {
    if (existing.expiresAt > Date.now()) return existing.value;
    cache.delete(key);
  }

  const value = await loader();
  cache.set(key, {
    value,
    expiresAt: Date.now() + ttlMs,
  });
  return value;
}

export function clearKnowledgeRequestCache(prefix?: string): void {
  if (!prefix) {
    cache.clear();
    return;
  }

  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}
