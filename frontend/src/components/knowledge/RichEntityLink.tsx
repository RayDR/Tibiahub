import { ArrowUpRight, Eye } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Dialog } from '../ui/Overlay';

export interface RichEntityTarget {
  canonicalName: string;
  entityType: 'npc' | 'location' | 'creature' | 'boss' | 'item' | 'huntZone' | 'quest' | 'mapPin';
  detailRoute: string;
  imageUrl?: string;
  summary?: string;
}

export default function RichEntityLink({ target, linkState }: { target: RichEntityTarget; linkState?: unknown }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return <>
    <div className="quest-codex__reference flex min-h-11 items-center justify-between gap-2 rounded-lg border px-3 py-2">
      <Link to={target.detailRoute} state={linkState} className="min-w-0 flex-1 font-medium hover:underline">
        {target.canonicalName}
      </Link>
      <button type="button" onClick={() => setOpen(true)} className="app-button-ghost app-button-sm shrink-0" aria-label={t('questDetail.previewEntity', { name: target.canonicalName })}>
        <Eye className="size-4" />
      </button>
    </div>
    <Dialog open={open} onClose={() => setOpen(false)} label={target.canonicalName} className="w-[min(92vw,28rem)] p-0">
      <div className="flex items-start gap-4 border-b border-line p-5">
        {target.imageUrl ? <img src={target.imageUrl} alt="" className="size-16 object-contain [image-rendering:pixelated]" /> : null}
        <div><p className="text-xs font-semibold uppercase tracking-wide text-primary">{t(`questDetail.entityTypes.${target.entityType}`)}</p><h3 className="mt-1 text-xl font-bold text-content-primary">{target.canonicalName}</h3></div>
      </div>
      <div className="p-5">
        <p className="text-sm text-content-secondary">{target.summary || t('questDetail.noCompactDetails')}</p>
        <div className="mt-5 flex justify-end gap-2"><button type="button" onClick={() => setOpen(false)} className="app-button-ghost app-button-sm">{t('common.close')}</button><Link to={target.detailRoute} state={linkState} onClick={() => setOpen(false)} className="app-button-primary app-button-sm">{t('questDetail.openEntity')}<ArrowUpRight className="size-4" /></Link></div>
      </div>
    </Dialog>
  </>;
}
