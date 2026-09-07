import type { LucideIcon } from 'lucide-react';
import { BookOpenCheck, Crown, Gem, MapPinned, Swords, UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { cyclopediaSections } from '../../config/cyclopediaSections';
import api from '../../services/api';

export type KnowledgeCategory =
  | 'creatures'
  | 'bosses'
  | 'items'
  | 'quests'
  | 'zones'
  | 'npcs';

type CategoryVisuals = Partial<Record<KnowledgeCategory, string>>;

type NpcVisualDirectoryPage = {
  items: Array<{
    canonical_id: string;
    media?: {
      status?: string;
      url?: string | null;
    };
  }>;
  total: number;
};

const fallbackIcons: Record<KnowledgeCategory, LucideIcon> = {
  creatures: Swords,
  bosses: Crown,
  items: Gem,
  quests: BookOpenCheck,
  zones: MapPinned,
  npcs: UserRound,
};

let visualCache: CategoryVisuals | null = null;
let visualRequest: Promise<CategoryVisuals> | null = null;

async function loadRandomNpcVisual(): Promise<string | undefined> {
  try {
    const { data: firstPage } = await api.get<NpcVisualDirectoryPage>('/npcs/directory', {
      params: { skip: 0, limit: 1 },
    });
    const total = Math.max(0, firstPage.total || 0);
    if (!total) return undefined;

    const sampleSize = Math.min(25, total);
    const maxSkip = Math.max(0, total - sampleSize);
    const skip = Math.floor(Math.random() * (maxSkip + 1));
    const { data: sample } = await api.get<NpcVisualDirectoryPage>('/npcs/directory', {
      params: { skip, limit: sampleSize },
    });
    const available = sample.items.filter(
      (npc) => npc.media?.status === 'cached' && npc.media.url,
    );
    if (!available.length) return undefined;

    const selected = available[Math.floor(Math.random() * available.length)];
    return selected.media?.url || undefined;
  } catch {
    return undefined;
  }
}

function loadCategoryVisuals(): Promise<CategoryVisuals> {
  if (visualCache) return Promise.resolve(visualCache);
  if (!visualRequest) {
    visualRequest = Promise.all([
      api
        .get<CategoryVisuals>('/catalog/category-visuals')
        .then(({ data }) => data || {})
        .catch(() => ({})),
      loadRandomNpcVisual(),
    ])
      .then(([visuals, npcVisual]) => {
        visualCache = npcVisual
          ? { ...visuals, npcs: npcVisual }
          : visuals;
        return visualCache;
      })
      .finally(() => {
        visualRequest = null;
      });
  }
  return visualRequest;
}

export function categoryForTab(value: string): KnowledgeCategory {
  return value === 'loot' ? 'items' : value as KnowledgeCategory;
}

export function KnowledgeCategoryMedia({
  category,
  label,
  className = 'size-9',
  mediaClassName = 'size-8',
}: {
  category: KnowledgeCategory;
  label: string;
  className?: string;
  mediaClassName?: string;
}) {
  const { t } = useTranslation();
  const [visuals, setVisuals] = useState<CategoryVisuals>(visualCache || {});
  const [failed, setFailed] = useState(false);
  const FallbackIcon = fallbackIcons[category];
  const categorySection = cyclopediaSections.find((section) => section.mode === category);
  const categoryLabel = categorySection ? t(categorySection.i18nLabel) : label;
  const useCategoryVisual = category !== 'npcs' || label === categoryLabel;
  const imageUrl = useCategoryVisual ? visuals[category] : undefined;

  useEffect(() => {
    let active = true;
    void loadCategoryVisuals().then((next) => {
      if (active) setVisuals(next);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => setFailed(false), [imageUrl]);

  return (
    <span
      title={label}
      aria-hidden="true"
      className={`grid shrink-0 place-items-center overflow-hidden rounded-lg bg-primary/10 text-primary ${className}`}
    >
      {imageUrl && !failed ? (
        <img
          src={imageUrl}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className={`object-contain [image-rendering:pixelated] ${mediaClassName}`}
        />
      ) : (
        <FallbackIcon className="size-1/2" aria-hidden="true" />
      )}
    </span>
  );
}

export default KnowledgeCategoryMedia;
