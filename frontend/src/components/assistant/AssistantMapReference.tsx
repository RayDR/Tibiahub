import { Map } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { AssistantMapReference as MapReference } from '../../types/assistant';

export default function AssistantMapReference({ map }: { map: MapReference }) {
  const { t } = useTranslation();
  return <figure className="overflow-hidden rounded-xl border border-line bg-surface-base/60">
    <img src={map.image_url} alt={map.name} className="max-h-72 w-full object-contain" loading="lazy" />
    <figcaption className="flex flex-wrap items-center gap-2 p-3 text-xs text-content-muted">
      <Map className="size-4 text-primary" />
      <span className="font-medium text-content-primary">{map.name}</span>
      <span>{t('assistant.route.verification', { state: map.verification_state, confidence: map.confidence })}</span>
    </figcaption>
  </figure>;
}
