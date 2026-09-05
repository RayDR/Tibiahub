import type { LucideIcon } from 'lucide-react';
import { BookOpenCheck, Crown, Gem, MapPinned, Swords, UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';

import api from '../../services/api';

export type KnowledgeCategory =
  | 'creatures'
  | 'bosses'
  | 'items'
  | 'quests'
  | 'zones'
  | 'npcs';

type CategoryVisuals = Partial<Record<KnowledgeCategory, string>>;

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

function loadCategoryVisuals(): Promise<CategoryVisuals> {
  if (visualCache) return Promise.resolve(visualCache);
  if (!visualRequest) {
    visualRequest = api
      .get<CategoryVisuals>('/catalog/category-visuals')
      .then(({ data }) => {
        visualCache = data || {};
        return visualCache;
      })
      .catch(() => {
        visualCache = {};
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
  const [visuals, setVisuals] = useState<CategoryVisuals>(visualCache || {});
  const [failed, setFailed] = useState(false);
  const FallbackIcon = fallbackIcons[category];
  const imageUrl = visuals[category];

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
