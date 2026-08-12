import { ArrowUpRight, ImageOff } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import type { AssistantEntityReference } from '../../types/assistant';
import { Dialog } from '../ui/Overlay';

export default function AssistantEntity({
  entity,
  variant = 'inline',
}: {
  entity: AssistantEntityReference;
  variant?: 'inline' | 'card';
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const entityTypeLabel = entity.entity_type === 'creature' && entity.metadata?.is_boss === true
    ? t('assistant.entity.types.boss')
    : t(`assistant.entity.types.${entity.entity_type}`);
  const usefulMetadataKeys = new Set(['hitpoints', 'experience', 'difficulty', 'city', 'min_level', 'item_type', 'category', 'level', 'occupation', 'location', 'kind', 'region', 'premium']);
  const metadata = Object.entries(entity.metadata || {})
    .filter(([key, value]) => key !== 'is_boss' && usefulMetadataKeys.has(key) && value != null && value !== '')
    .slice(0, 2);

  return <>
    <button
      type="button"
      onClick={() => setOpen(true)}
      className={variant === 'inline'
        ? 'mx-0.5 inline-flex min-h-7 items-center gap-1.5 rounded-full border border-primary/35 bg-primary/10 px-2 py-0.5 align-baseline text-sm font-semibold text-primary hover:border-primary/70 hover:bg-primary/20'
        : 'group flex min-h-24 w-full items-center gap-3 rounded-xl border border-transparent bg-surface-active/45 p-3 text-left shadow-sm transition hover:bg-surface-active focus-visible:border-primary/60'}
      aria-label={t('assistant.entity.inspect', { name: entity.canonical_name })}
    >
      {entity.image_url ? <span className={variant === 'card' ? 'grid size-16 shrink-0 place-items-center rounded-lg bg-surface-base/55' : undefined}><img src={entity.image_url} alt="" className={variant === 'inline' ? 'size-5 object-contain [image-rendering:pixelated]' : 'size-14 object-contain [image-rendering:pixelated]'} loading="lazy" /></span> : null}
      <span className={variant === 'card' ? 'min-w-0' : undefined}>
        <span className={variant === 'card' ? 'block truncate font-semibold text-content-primary' : undefined}>{entity.canonical_name}</span>
        {variant === 'card' ? <span className="block text-xs capitalize text-content-muted">{entityTypeLabel}</span> : null}
        {variant === 'card' && metadata.length ? <span className="mt-1 block truncate text-xs text-content-secondary">{metadata.map(([key, value]) => `${t(`assistant.entity.metadata.${key}`)}: ${String(value)}`).join(' · ')}</span> : null}
      </span>
    </button>

    <Dialog open={open} onClose={() => setOpen(false)} label={entity.canonical_name} className="w-[min(92vw,30rem)] p-0">
      <div className="flex items-start gap-4 border-b border-line p-5">
        <div className="grid size-20 shrink-0 place-items-center rounded-xl bg-primary/10">
          {entity.image_url
            ? <img src={entity.image_url} alt="" className="size-16 object-contain [image-rendering:pixelated]" />
            : <ImageOff className="size-7 text-content-muted" />}
        </div>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">{entityTypeLabel}</p>
          <h3 className="mt-1 text-xl font-bold text-content-primary">{entity.canonical_name}</h3>
        </div>
      </div>
      <div className="p-5">
        {metadata.length > 0 ? <dl className="grid gap-2 sm:grid-cols-2">
          {metadata.map(([key, value]) => <div key={key} className="rounded-lg bg-surface-base/60 p-3">
            <dt className="text-xs capitalize text-content-muted">{key.split('_').join(' ')}</dt>
            <dd className="mt-1 text-sm text-content-primary">{String(value)}</dd>
          </div>)}
        </dl> : <p className="text-sm text-content-secondary">{t('assistant.entity.noCompactDetails')}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={() => setOpen(false)} className="app-button-ghost app-button-sm">{t('assistant.close')}</button>
          <Link to={entity.detail_route} className="app-button-primary app-button-sm" onClick={() => setOpen(false)}>
            {t('assistant.entity.openFull')}<ArrowUpRight className="size-4" />
          </Link>
        </div>
      </div>
    </Dialog>
  </>;
}
