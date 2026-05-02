import React, { useState } from 'react';
import { ImageOff } from 'lucide-react';

interface ImageWithFallbackProps {
  src?: string | null;
  alt: string;
  fallbackLabel?: string;
  className?: string;
  containerClassName?: string;
}

const ImageWithFallback: React.FC<ImageWithFallbackProps> = ({
  src,
  alt,
  fallbackLabel = 'No image',
  className = '',
  containerClassName = '',
}) => {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div className={`flex items-center justify-center rounded-lg bg-slate-800 text-slate-400 ${containerClassName}`}>
        <div className="flex flex-col items-center gap-1">
          <ImageOff size={18} />
          <span className="text-[10px] uppercase tracking-wide">{fallbackLabel}</span>
        </div>
      </div>
    );
  }

  return <img src={src} alt={alt} loading="lazy" className={className} onError={() => setFailed(true)} />;
};

export default ImageWithFallback;
