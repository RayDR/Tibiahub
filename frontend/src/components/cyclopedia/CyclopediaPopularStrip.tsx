import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import CompactEntityStrip, {
  type CompactEntityStripItem,
} from '../CompactEntityStrip';
import {
  creaturesApi,
  huntZonesApi,
  itemsApi,
  questsApi,
} from '../../services/api';
import { discoveryApi } from '../../services/discovery';
import {
  createCyclopediaRouteState,
  saveCyclopediaReturnTarget,
} from '../../utils/cyclopediaNavigation';
import { availableItemMediaUrl } from '../../utils/entityMedia';

export type CyclopediaPopularMode =
  | 'creatures'
  | 'bosses'
  | 'items'
  | 'quests'
  | 'zones'
  | 'npcs';

async function loadPopular(
  mode: CyclopediaPopularMode,
  signal: AbortSignal,
): Promise<CompactEntityStripItem[]> {
  if (mode === 'creatures') {
    const rows = await creaturesApi.getPopular(12, signal);
    return rows.map((row) => ({
      id: `popular:creature:${row.id}`,
      name: row.name,
      subtitle: row.experience != null ? `${row.experience.toLocaleString()} EXP` : undefined,
      to: `/creatures/${row.slug || row.id}`,
      imageUrl: `/api/v1/creatures/${row.id}/image?placeholder=false`,
    }));
  }

  if (mode === 'bosses') {
    const rows = await creaturesApi.getPopularBosses(12, signal);
    return rows.map((row) => ({
      id: `popular:boss:${row.id}`,
      name: row.name,
      subtitle: row.difficulty || undefined,
      to: `/creatures/${row.slug || row.id}`,
      imageUrl: `/api/v1/creatures/${row.id}/image?placeholder=false`,
    }));
  }

  if (mode === 'items') {
    const rows = await itemsApi.getPopular(12, signal);
    return rows.map((row) => ({
      id: `popular:item:${row.normalized_name}`,
      name: row.item_name,
      subtitle: row.drops?.length != null ? `${row.drops.length} drops` : undefined,
      to: `/items/${row.slug || row.normalized_name.split(' ').join('-')}`,
      imageUrl: availableItemMediaUrl(row.media),
    }));
  }

  if (mode === 'quests') {
    const rows = await questsApi.getHighlights(12, signal);
    return rows.map((row) => ({
      id: `popular:quest:${row.id || row.slug || row.name}`,
      name: row.name,
      subtitle: row.group_name || undefined,
      to: row.slug || row.id ? `/quests/${row.slug || row.id}` : '/cyclopedia?tab=quests',
    }));
  }

  if (mode === 'zones') {
    const rows = await huntZonesApi.getHighlights(12, signal);
    return rows.map((row) => ({
      id: `popular:zone:${row.id}`,
      name: row.name,
      subtitle: row.region || row.city || undefined,
      to: `/hunt-zones/${row.slug || row.id}`,
      imageUrl: `/api/v1/hunt-zones/${row.id}/map-image`,
    }));
  }

  // NPC popularity is sourced only from the shared discovery read model so we
  // do not mislabel an alphabetical directory page as "popular".
  const discovery = await discoveryApi.load(signal);
  const seen = new Set<string>();
  const cards: CompactEntityStripItem[] = [];
  for (const row of [...discovery.trending, ...discovery.latest_knowledge]) {
    if ((row.entity_type || '').toLowerCase() !== 'npc') continue;
    const key = String(row.id || row.slug || row.name).trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    cards.push({
      id: `popular:npc:${key}`,
      name: row.name,
      subtitle: row.summary || undefined,
      to: `/npcs/${row.slug || row.id}`,
      imageUrl: row.image_url || undefined,
    });
    if (cards.length >= 12) break;
  }
  return cards;
}

export default function CyclopediaPopularStrip({
  mode,
}: {
  mode: CyclopediaPopularMode;
}) {
  const { t, i18n } = useTranslation();
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
    const controller = new AbortController();
    setItems([]);

    void loadPopular(mode, controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) setItems(rows);
      })
      .catch(() => {
        if (!controller.signal.aborted) setItems([]);
      });

    return () => controller.abort();
  }, [mode]);

  if (items.length === 0) return null;

  const title = t('cyclopedia.discovery.popular', {
    defaultValue: i18n.resolvedLanguage?.startsWith('es') ? 'Populares' : 'Popular',
  });

  return (
    <div
      className="cyclopedia-context-rail rounded-2xl border border-line bg-surface-raised/60 p-4"
      data-cyclopedia-context="popular"
    >
      <CompactEntityStrip
        title={title}
        items={items}
        variant="rail"
        nudgeSessionKey={`popular-${mode}`}
        linkState={routeState}
        onNavigate={() => saveCyclopediaReturnTarget(returnPath)}
      />
    </div>
  );
}
