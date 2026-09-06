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

type PersonalHistoryMode = 'items' | 'zones';

interface VisitAggregate {
  count: number;
  latest: string;
  name: string;
  slug: string;
  mediaUrl?: string;
}

function expectedActivity(mode: PersonalHistoryMode) {
  return mode === 'items' ? 'view_item' : 'view_zone';
}

function toCard(
  mode: PersonalHistoryMode,
  entityId: string,
  visit: VisitAggregate,
  visitsLabel: (count: number) => string,
): CompactEntityStripItem {
  if (mode === 'items') {
    return {
      id: `visited:items:${entityId}`,
      name: visit.name,
      subtitle: visitsLabel(visit.count),
      to: `/items/${visit.slug || entityId}`,
      imageUrl: availableItemMediaUrl(
        visit.mediaUrl
          ? { status: 'available', url: visit.mediaUrl } satisfies ItemMedia
          : undefined,
      ),
    };
  }

  return {
    id: `visited:zones:${entityId}`,
    name: visit.name,
    subtitle: visitsLabel(visit.count),
    to: `/hunt-zones/${visit.slug || entityId}`,
    imageUrl: `/api/v1/hunt-zones/${entityId}/map-image?placeholder=false`,
  };
}

export default function CyclopediaPersonalHistoryStrip({
  mode,
}: {
  mode: PersonalHistoryMode;
}) {
  const { t } = useTranslation();
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
    if (!isAuthenticated) {
      setItems([]);
      return undefined;
    }

    const controller = new AbortController();
    const activityType = expectedActivity(mode);

    void activityApi
      .getMine(100, controller.signal)
      .then((activity) => {
        if (controller.signal.aborted) return;

        const visits = new Map<string, VisitAggregate>();
        for (const entry of activity) {
          if (entry.activity_type !== activityType) continue;

          const entityId = String(entry.entity_id || '').trim();
          const name = String(entry.metadata?.name || '').trim();
          if (!entityId || !name) continue;

          const current = visits.get(entityId);
          const latest =
            current && current.latest > entry.created_at
              ? current.latest
              : entry.created_at;

          visits.set(entityId, {
            count: (current?.count || 0) + 1,
            latest,
            name,
            slug:
              String(entry.metadata?.slug || '').trim() ||
              current?.slug ||
              '',
            mediaUrl:
              String(entry.metadata?.media_url || '').trim() ||
              current?.mediaUrl,
          });
        }

        const cards = [...visits.entries()]
          .sort(
            ([, left], [, right]) =>
              right.count - left.count ||
              right.latest.localeCompare(left.latest),
          )
          .slice(0, 5)
          .map(([entityId, visit]) =>
            toCard(mode, entityId, visit, (count) =>
              t('cyclopedia.cards.visits', { count }),
            ),
          );

        setItems(cards);
      })
      .catch(() => {
        if (!controller.signal.aborted) setItems([]);
      });

    return () => controller.abort();
  }, [isAuthenticated, mode, t]);

  return (
    <CompactEntityStrip
      title={t('cyclopedia.cards.mostVisited')}
      items={items}
      variant="chips"
      linkState={routeState}
      onNavigate={() => saveCyclopediaReturnTarget(returnPath)}
    />
  );
}
