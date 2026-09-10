import React, { useEffect, useState } from 'react';
import { ImageOff } from 'lucide-react';

import BrandCategoryFallbackIcon, { type BrandCategoryKey } from './icons/BrandCategoryFallbackIcon';

export type MediaFallbackKind = 'image' | 'item' | 'creature' | 'boss' | 'npc' | 'quest' | 'zone';

interface ImageWithFallbackProps {
  src?: string | null;
  alt: string;
  fallbackLabel?: string;
  fallbackKind?: MediaFallbackKind;
  className?: string;
  containerClassName?: string;
}

const failedMediaUrls = new Set<string>();

const brandCategoryForFallback: Partial<Record<MediaFallbackKind, BrandCategoryKey>> = {
  item: 'items',
  creature: 'creatures',
  boss: 'bosses',
  npc: 'npcs',
  quest: 'quests',
  zone: 'zones',
};

const ImageWithFallback: React.FC<ImageWithFallbackProps> = ({
  src,
  alt,
  fallbackLabel = 'No image',
  fallbackKind,
  className = '',
  containerClassName = '',
}) => {
  const [failed, setFailed] = useState(() => Boolean(src && failedMediaUrls.has(src)));

  useEffect(() => {
    setFailed(Boolean(src && failedMediaUrls.has(src)));
  }, [src]);

  if (!src || failed) {
    const resolvedFallbackKind = fallbackKind || (fallbackLabel === alt ? 'item' : 'image');
    const brandCategory = brandCategoryForFallback[resolvedFallbackKind];

    return (
      <div
        className={`relative flex items-center justify-center overflow-hidden rounded-lg bg-surface text-primary ${containerClassName}`}
        role="img"
        aria-label={fallbackLabel || alt}
      >
        {brandCategory ? (
          <BrandCategoryFallbackIcon category={brandCategory} className="size-1/2 max-h-12 max-w-12" />
        ) : (
          <ImageOff size={20} className="text-content-secondary" aria-hidden="true" />
        )}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={className}
      onError={() => {
        failedMediaUrls.add(src);
        setFailed(true);
      }}
    />
  );
};

export default ImageWithFallback;
