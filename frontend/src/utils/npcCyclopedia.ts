import type { NpcDirectoryItem, NpcDirectoryPage, NpcMedia } from '../types';

export const NPC_CYCLOPEDIA_PAGE_SIZE = 20;

export function mergeNpcRows(
  current: NpcDirectoryItem[],
  incoming: NpcDirectoryItem[],
): NpcDirectoryItem[] {
  const byCanonicalId = new Map(
    current.map((npc) => [npc.canonical_id, npc]),
  );
  for (const npc of incoming) {
    if (!byCanonicalId.has(npc.canonical_id)) {
      byCanonicalId.set(npc.canonical_id, npc);
    }
  }
  return [...byCanonicalId.values()];
}

export function npcPageHasMore(page: NpcDirectoryPage): boolean {
  return page.skip + page.items.length < page.total;
}

export function localNpcMediaUrl(media: NpcMedia): string | null {
  if (media.status !== 'available' && media.status !== 'cached') return null;
  const value = media.url?.trim();
  return value?.startsWith('/api/v1/npcs/') ? value : null;
}

export function buildLegacyNpcBrowseRedirect(search: string): string {
  const legacy = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
  const target = new URLSearchParams({ tab: 'npcs' });
  const query = legacy.get('q')?.trim();
  const location = legacy.get('location')?.trim();
  if (query) target.set('q', query);
  if (location) target.set('location', location);
  return `/cyclopedia?${target.toString()}`;
}
