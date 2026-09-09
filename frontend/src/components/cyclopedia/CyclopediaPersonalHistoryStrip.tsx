import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import CompactEntityStrip, {
  type CompactEntityStripItem,
} from '../CompactEntityStrip';
import { useAuth } from '../../context/AuthContext';
import { activityApi } from '../../services/activity';
import {
  createCyclopediaRouteState,
  saveCyclopediaReturnTarget,
} from '../../utils/cyclopediaNavigation';
import type { ItemMedia } from '../../types';
import { availableItemMediaUrl } from '../../utils/entityMedia';

export type CyclopediaPersonalHistoryMode =
  | 'creatures'
  | 'bosses'
  | 'items'
  | 'quests'
  | 'zones'
  | 'npcs';

interface VisitAggregate {
  latest: string;
  name: string;
  slug: string;
  mediaUrl?: string;
}

interface StoredRecentCard {
  id?: string;
  name?: string;
  to?: string;
  imageUrl?: string;
  createdAt?: string;
}

const activityByMode: Record<CyclopediaPersonalHistoryMode, string> = {
  creatures: 'view_creature',
  bosses: 'view_boss',
  items: 'view_item',
  quests: 'view_quest',
  zones: 'view_zone',
  npcs: 'view_npc',
};

function itemMedia(mediaUrl?: string): string | undefined {
  return availableItemMediaUrl(
    mediaUrl
      ? { status: 'available', url: mediaUrl } satisfies ItemMedia
      : undefined,
  );
}

function toCard(
  mode: CyclopediaPersonalHistoryMode,
  entityId: string,
  visit: VisitAggregate,
): CompactEntityStripItem {
  if (mode === 'creatures' || mode === 'bosses') {
    return {
      id: `recent:${mode}:${entityId}`,
      name: visit.name,
      to: `/creatures/${visit.slug || entityId}`,
      imageUrl: `/api/v1/creatures/${entityId}/image?placeholder=false`,
    };
  }

  if (mode === 'items') {
    return {
      id: `recent:items:${entityId}`,
      name: visit.name,
      to: `/items/${visit.slug || entityId}`,
      imageUrl: itemMedia(visit.mediaUrl),
    };
  }

  if (mode === 'quests') {
    return {
      id: `recent:quests:${entityId}`,
      name: visit.name,
      to: `/quests/${visit.slug || entityId}`,
    };
  }

  if (mode === 'zones') {
    return {
      id: `recent:zones:${entityId}`,
      name: visit.name,
      to: `/hunt-zones/${visit.slug || entityId}`,
      imageUrl: `/api/v1/hunt-zones/${entityId}/map-image?placeholder=false`,
    };
  }

  return {
    id: `recent:npcs:${entityId}`,
    name: visit.name,
    to: `/npcs/${visit.slug || entityId}`,
    imageUrl: visit.mediaUrl,
  };
}

function loadLocalRecent(
  mode: CyclopediaPersonalHistoryMode,
): CompactEntityStripItem[] {
  try {
    const raw = window.localStorage.getItem(`cyclopedia_recent_${mode}`);
    if (!raw) return [];

    const parsed = JSON.parse(raw) as StoredRecentCard[];
    if (!Array.isArray(parsed)) return [];

    return parsed
      .filter((item) => item?.name && item?.to)
      .sort((left, right) =>
        String(right.createdAt || '').localeCompare(String(left.createdAt || '')),
      )
      .slice(0, 6)
      .map((item, index) => ({
        id: item.id || `local:${mode}:${index}:${item.name}`,
        name: String(item.name),
        to: String(item.to),
        imageUrl: item.imageUrl ? String(item.imageUrl) : undefined,
      }));
  } catch {
    return [];
  }
}

export default function CyclopediaPersonalHistoryStrip({
  mode,
}: {
  mode: CyclopediaPersonalHistoryMode;
}) {
  const { t, i18n } = useTranslation();
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const [items, setItems] = useState<CompactEntityStripItem[]>([]);

  const returnPath = useMemo(
    () => `${location.pathname}${location.search}`,
    [location.pathname, location.search],
  );
  const routeState = useMemo(
    () => createCyclopediaRouteState(returnPath),
    [returnPath],
  );

  useEffect(() => {
    const localFallback = loadLocalRecent(mode);
    setItems(localFallback);

    if (!isAuthenticated) return undefined;

    const controller = new AbortController();
    const activityType = activityByMode[mode];

    void activityApi
      .getMine(120, controller.signal)
      .then((activity) => {
        if (controller.signal.aborted) return;

        const visits = new Map<string, VisitAggregate>();
        for (const entry of activity) {
          if (entry.activity_type !== activityType) continue;

          const entityId = String(entry.entity_id || '').trim();
          const name = String(entry.metadata?.name || '').trim();
          if (!entityId || !name) continue;

          const current = visits.get(entityId);
          const newest = !current || entry.created_at > current.latest;
          if (!newest) continue;

          visits.set(entityId, {
            latest: entry.created_at,
            name,
            slug: String(entry.metadata?.slug || '').trim(),
            mediaUrl: String(entry.metadata?.media_url || '').trim() || undefined,
          });
        }

        const cards = [...visits.entries()]
          .sort(([, left], [, right]) => right.latest.localeCompare(left.latest))
          .slice(0, 6)
          .map(([entityId, visit]) => toCard(mode, entityId, visit));

        setItems(cards.length ? cards : localFallback);
      })
      .catch(() => {
        if (!controller.signal.aborted) setItems(localFallback);
      });

    return () => controller.abort();
  }, [isAuthenticated, mode]);

  if (items.length === 0) return null;

  const title = t('cyclopedia.cards.recentlyViewed', {
    defaultValue: i18n.resolvedLanguage?.startsWith('es')
      ? 'Vistos recientemente'
      : 'Recently viewed',
  });

  return (
    <div data-cyclopedia-context="recent">
      <CompactEntityStrip
        title={title}
        items={items}
        variant="chips"
        linkState={routeState}
        onNavigate={() => saveCyclopediaReturnTarget(returnPath)}
      />
    </div>
  );
}
