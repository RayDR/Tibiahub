import React, { useEffect, useState } from 'react';
import { ImageOff } from 'lucide-react';

import bossPlaceholder from '../assets/placeholders/boss.svg';
import creaturePlaceholder from '../assets/placeholders/creature.svg';
import lootItemPlaceholder from '../assets/placeholders/loot-item.svg';

export type MediaFallbackKind = 'image' | 'item' | 'creature' | 'boss';

interface ImageWithFallbackProps {
  src?: string | null;
  alt: string;
  fallbackLabel?: string;
  fallbackKind?: MediaFallbackKind;
  className?: string;
  containerClassName?: string;
}

const failedMediaUrls = new Set<string>();

const themedFallbacks: Partial<Record<MediaFallbackKind, string>> = {
  item: lootItemPlaceholder,
  creature: creaturePlaceholder,
  boss: bossPlaceholder,
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
    const themedFallback = themedFallbacks[resolvedFallbackKind];

    return (
      <div
        className={`relative flex items-center justify-center overflow-hidden rounded-lg bg-surface text-content-secondary ${containerClassName}`}
        role="img"
        aria-label={fallbackLabel || alt}
      >
        {themedFallback ? (
          <img
            src={themedFallback}
            alt=""
            aria-hidden="true"
            draggable={false}
            className="size-full object-contain p-1"
          />
        ) : (
          <ImageOff size={20} aria-hidden="true" />
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
