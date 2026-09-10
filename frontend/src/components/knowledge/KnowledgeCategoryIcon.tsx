import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import BrandCategoryFallbackIcon from '../icons/BrandCategoryFallbackIcon';
import { cyclopediaSections } from '../../config/cyclopediaSections';
import api, { tibiaApi } from '../../services/api';
import type { BoostedCreatureProjection } from '../../types';

export type KnowledgeCategory =
  | 'creatures'
  | 'bosses'
  | 'items'
  | 'quests'
  | 'zones'
  | 'npcs';

type CategoryVisuals = Partial<Record<KnowledgeCategory, string>>;
type CategoryVisualResponse = CategoryVisuals & { visual_day?: string };

let visualCache: CategoryVisuals | null = null;
let visualCacheDay: string | null = null;
let visualRequest: Promise<CategoryVisuals> | null = null;

const utcDay = () => new Date().toISOString().slice(0, 10);

function boostedMediaUrl(projection?: BoostedCreatureProjection | null): string | undefined {
  if (!projection) return undefined;
  if (projection.media?.status === 'available' && projection.media.url) {
    return projection.media.url;
  }
  if (projection.resolution_state === 'resolved' && projection.id != null) {
    return `/api/v1/creatures/${projection.id}/image?placeholder=false`;
  }
  return undefined;
}

function loadCategoryVisuals(): Promise<CategoryVisuals> {
  const today = utcDay();
  if (visualCache && visualCacheDay === today) return Promise.resolve(visualCache);

  if (!visualRequest) {
    const categoryRequest = api
      .get<CategoryVisualResponse>('/catalog/category-visuals/daily')
      .then(({ data }) => data || {})
      .catch(() => ({} as CategoryVisualResponse));
    const boostedRequest = tibiaApi.getBoosted().catch(() => null);

    visualRequest = Promise.all([categoryRequest, boostedRequest])
      .then(([data, boosted]) => {
        visualCache = {
          creatures: boostedMediaUrl(boosted?.creature) || data.creatures || undefined,
          bosses: boostedMediaUrl(boosted?.boss) || data.bosses || undefined,
          items: data.items || undefined,
          quests: data.quests || undefined,
          zones: data.zones || undefined,
          npcs: data.npcs || undefined,
        };
        visualCacheDay = data.visual_day || today;
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
  preferCategoryVisual,
}: {
  category: KnowledgeCategory;
  label: string;
  className?: string;
  mediaClassName?: string;
  preferCategoryVisual?: boolean;
}) {
  const { t } = useTranslation();
  const [visuals, setVisuals] = useState<CategoryVisuals>(
    visualCacheDay === utcDay() ? visualCache || {} : {},
  );
  const [failed, setFailed] = useState(false);
  const categorySection = cyclopediaSections.find((section) => section.mode === category);
  const categoryLabel = categorySection ? t(categorySection.i18nLabel) : label;
  const useCategoryVisual = preferCategoryVisual ?? label === categoryLabel;
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
        <BrandCategoryFallbackIcon category={category} className="size-1/2" />
      )}
    </span>
  );
}

export default KnowledgeCategoryMedia;
