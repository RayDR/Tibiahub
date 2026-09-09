import { ArrowUpRight, BookOpenCheck, MapPin, PackageOpen, Route } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import type { NpcDirectoryItem } from '../types';
import { localNpcMediaUrl } from '../utils/npcCyclopedia';
import BrandCategoryFallbackIcon from './icons/BrandCategoryFallbackIcon';
import { useOptionalCyclopediaPreviewSelection } from './cyclopedia/CyclopediaPreviewSelectionContext';
import './NpcCard.css';

interface NpcCardProps {
  npc: NpcDirectoryItem;
  linkState?: unknown;
  onNavigate?: () => void;
}

function NpcPortrait({ npc, large = false }: { npc: NpcDirectoryItem; large?: boolean }) {
  const mediaUrl = localNpcMediaUrl(npc.media);
  const [failed, setFailed] = useState(false);

  useEffect(() => setFailed(false), [mediaUrl]);

  return (
    <span className={large ? 'npc-card-portrait npc-card-portrait--large' : 'grid size-20 shrink-0 place-items-center overflow-hidden rounded-xl bg-primary/[0.07] text-primary'}>
      {mediaUrl && !failed ? (
        <img
          src={mediaUrl}
          alt=""
          aria-hidden="true"
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className={large ? 'size-full object-contain p-2 [image-rendering:pixelated]' : 'max-h-20 max-w-full object-contain p-1 [image-rendering:pixelated]'}
        />
      ) : (
        <BrandCategoryFallbackIcon category="npcs" className={large ? 'size-14 opacity-80' : 'size-8'} />
      )}
    </span>
  );
}

export default function NpcCard({ npc, linkState, onNavigate }: NpcCardProps) {
  const { t } = useTranslation();
  const preview = useOptionalCyclopediaPreviewSelection();
  const isCyclopedia = Boolean(preview);
  const selected = preview?.selection?.kind === 'npc' && preview.selection.identifier === npc.canonical_id;

  if (!isCyclopedia) {
    return (
      <Link
        data-npc-card
        to={`/npcs/${npc.canonical_id}`}
        state={linkState}
        onClick={onNavigate}
        aria-label={npc.name}
        className="group flex h-full min-h-40 flex-col items-center justify-center rounded-xl border border-line bg-surface-base/70 p-3 text-center shadow-sm transition hover:-translate-y-0.5 hover:border-primary/60 hover:bg-surface-raised hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary motion-reduce:transform-none"
      >
        <NpcPortrait npc={npc} />
        <span className="mt-2 line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-content-primary">
          {npc.name}
        </span>
      </Link>
    );
  }

  const tradeCount = (npc.buys_count || 0) + (npc.sells_count || 0);
  const subtitle = npc.title || npc.occupation || npc.location_name;

  return (
    <article
      data-npc-card
      data-cyclopedia-npc-card="true"
      data-npc-identifier={npc.canonical_id}
      data-selected={selected ? 'true' : 'false'}
      className="npc-cyclopedia-card"
    >
      <button
        type="button"
        className="npc-cyclopedia-card__select"
        onClick={() => preview?.select({ kind: 'npc', identifier: npc.canonical_id })}
        aria-pressed={selected}
        aria-label={npc.name}
      >
        <NpcPortrait npc={npc} large />
        <div className="npc-cyclopedia-card__identity">
          <strong className="npc-cyclopedia-card__name">{npc.name}</strong>
          {subtitle ? <span className="npc-cyclopedia-card__subtitle">{subtitle}</span> : null}
        </div>

        <div className="npc-cyclopedia-card__facts">
          <span><PackageOpen className="size-3.5" />{t('npcDetail.trade')}<strong>{tradeCount}</strong></span>
          <span><BookOpenCheck className="size-3.5" />{t('npcDetail.quests')}<strong>{npc.quest_count || 0}</strong></span>
          <span><Route className="size-3.5" />{t('npcDetail.travel')}<strong>{npc.destination_count || 0}</strong></span>
        </div>

        <div className="npc-cyclopedia-card__location">
          <MapPin className="size-3.5 shrink-0 text-primary" />
          <span className="truncate">{npc.location_name || t('npcDetail.unknownLocation')}</span>
          {npc.map_available ? <span className="npc-cyclopedia-card__mapped">{t('npcDetail.openMap')}</span> : null}
        </div>
      </button>

      <Link
        to={`/npcs/${npc.canonical_id}`}
        state={linkState}
        onClick={onNavigate}
        className="npc-cyclopedia-card__details"
      >
        {t('plannerRecovery.details')} <ArrowUpRight className="size-3.5" />
      </Link>
    </article>
  );
}
