import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';

interface CyclopediaTabMediaProps {
  imageUrl?: string;
  label: string;
  fallback: ReactNode;
}

export default function CyclopediaTabMedia({
  imageUrl,
  label,
  fallback,
}: CyclopediaTabMediaProps) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [imageUrl]);

  return (
    <span
      title={label}
      aria-hidden="true"
      className="grid size-7 shrink-0 place-items-center overflow-hidden rounded-lg bg-primary/10 text-primary"
    >
      {imageUrl && !failed ? (
        <img
          src={imageUrl}
          alt=""
          loading="eager"
          decoding="async"
          onError={() => setFailed(true)}
          className="size-6 object-contain [image-rendering:pixelated]"
        />
      ) : (
        fallback
      )}
    </span>
  );
}
