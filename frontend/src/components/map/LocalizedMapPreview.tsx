import { MapPin } from 'lucide-react';
import { useMemo, useState } from 'react';

import type { HuntZoneSpatial } from '../../types';

interface LocalizedMapPreviewProps {
  spatial?: HuntZoneSpatial | null;
  label: string;
  className?: string;
  marker?: boolean;
}

function numericBounds(value?: Record<string, unknown> | null) {
  if (!value) return null;
  const number = (...keys: string[]) => {
    const candidate = keys.map((key) => value[key]).find((item) => typeof item === 'number');
    return typeof candidate === 'number' && Number.isFinite(candidate) ? candidate : null;
  };
  const minX = number('min_x', 'minX'); const minY = number('min_y', 'minY');
  const maxX = number('max_x', 'maxX'); const maxY = number('max_y', 'maxY');
  return minX != null && minY != null && maxX != null && maxY != null && maxX > minX && maxY > minY
    ? { minX, minY, maxX, maxY }
    : null;
}

function isLocalFloorImage(value: string): boolean {
  try {
    const url = new URL(value, window.location.origin);
    return url.origin === window.location.origin && /\/api\/v1\/map\/floors\/\d+\/image$/.test(url.pathname);
  } catch {
    return false;
  }
}

export default function LocalizedMapPreview({ spatial, label, className = '', marker = true }: LocalizedMapPreviewProps) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const projection = useMemo(() => {
    const map = spatial?.world_map;
    const bounds = numericBounds(map?.bounds);
    const imageUrl = map?.image_url;
    if (!map || !bounds || !imageUrl || !isLocalFloorImage(imageUrl) || spatial?.x == null || spatial.y == null) return null;
    if (spatial.x < bounds.minX || spatial.x > bounds.maxX || spatial.y < bounds.minY || spatial.y > bounds.maxY) return null;
    const scale = 1.15;
    return {
      imageUrl,
      width: map.width * scale,
      height: map.height * scale,
      x: ((spatial.x - bounds.minX) / (bounds.maxX - bounds.minX)) * map.width * scale,
      y: ((spatial.y - bounds.minY) / (bounds.maxY - bounds.minY)) * map.height * scale,
    };
  }, [spatial]);

  if (!projection || failedUrl === projection.imageUrl) {
    return <div className={`bg-gradient-to-br from-primary/15 via-surface-base to-surface-raised ${className}`} aria-label={label} />;
  }

  return <div className={`relative overflow-hidden bg-surface-base ${className}`} role="img" aria-label={label}>
    <img
      src={projection.imageUrl}
      alt=""
      loading="lazy"
      draggable={false}
      onError={() => setFailedUrl(projection.imageUrl)}
      className="pointer-events-none absolute max-w-none select-none [image-rendering:pixelated]"
      style={{
        width: projection.width,
        height: projection.height,
        left: `calc(50% - ${projection.x}px)`,
        top: `calc(50% - ${projection.y}px)`,
      }}
    />
    {marker ? <span className="pointer-events-none absolute left-1/2 top-1/2 grid size-8 -translate-x-1/2 -translate-y-full place-items-center rounded-full border border-line-strong bg-primary text-content-on-primary shadow-lg"><MapPin size={17} fill="currentColor" /></span> : null}
  </div>;
}
