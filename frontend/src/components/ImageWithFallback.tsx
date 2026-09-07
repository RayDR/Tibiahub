import React, { useEffect, useState } from 'react';
import { ImageOff, Package } from 'lucide-react';

interface ImageWithFallbackProps {
  src?: string | null;
  alt: string;
  fallbackLabel?: string;
  fallbackKind?: 'image' | 'item';
  className?: string;
  containerClassName?: string;
}

const failedMediaUrls = new Set<string>();

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
    const FallbackIcon = resolvedFallbackKind === 'item' ? Package : ImageOff;

    return (
      <div
        className={`flex items-center justify-center rounded-lg bg-surface text-content-secondary ${containerClassName}`}
        role="img"
        aria-label={fallbackLabel}
      >
        <FallbackIcon size={20} aria-hidden="true" />
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
