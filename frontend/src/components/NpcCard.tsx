import { ArrowUpRight, BookOpenCheck, MapPin, PackageOpen, Route, UserRound } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
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

type NpcCardServiceTone = 'success' | 'info' | 'warning' | 'neutral';
interface NpcCardService {
  key: string;
  label: string;
  tone: NpcCardServiceTone;
  icon: ReactNode;
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
          className={large ? 'size-full object-contain [image-rendering:pixelated]' : 'max-h-20 max-w-full object-contain p-1 [image-rendering:pixelated]'}
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
  const services: NpcCardService[] = [];

  if (tradeCount > 0) {
    services.push({
      key: 'trade',
      label: t('npcDetail.trade'),
      tone: 'success',
      icon: <PackageOpen className="size-3" />,
    });
  }

  if ((npc.destination_count || 0) > 0) {
    services.push({
      key: 'travel',
      label: t('npcDetail.travel'),
      tone: 'info',
      icon: <Route className="size-3" />,
    });
  }

  if ((npc.quest_count || 0) > 0) {
    services.push({
      key: 'quests',
      label: t('npcDetail.quests'),
      tone: 'warning',
      icon: <BookOpenCheck className="size-3" />,
    });
  }

  if (!services.length && (npc.occupation || npc.title)) {
    services.push({
      key: 'occupation',
      label: npc.occupation || npc.title || '',
      tone: 'neutral',
      icon: <UserRound className="size-3" />,
    });
  }

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
        <div className="npc-cyclopedia-card__media">
          <NpcPortrait npc={npc} large />
          {npc.map_available ? (
            <span className="npc-cyclopedia-card__map-status" title={t('npcDirectory.card.mapped')}>
              <MapPin className="size-3.5" />
            </span>
          ) : null}
        </div>

        <div className="npc-cyclopedia-card__identity">
          <strong className="npc-cyclopedia-card__name">{npc.name}</strong>
          <span className="npc-cyclopedia-card__location">
            <MapPin className="size-3 shrink-0" />
            <span>{npc.location_name || t('npcDetail.unknownLocation')}</span>
          </span>
        </div>

        {services.length ? (
          <div className="npc-cyclopedia-card__services" aria-label={t('npcDirectory.subtitle')}>
            {services.slice(0, 2).map((service) => (
              <span key={service.key} className="npc-cyclopedia-card__service" data-tone={service.tone} title={service.label}>
                {service.icon}
                <span>{service.label}</span>
              </span>
            ))}
          </div>
        ) : null}
      </button>

      <Link
        to={`/npcs/${npc.canonical_id}`}
        state={linkState}
        onClick={onNavigate}
        className="npc-cyclopedia-card__details"
        aria-label={t('npcDirectory.card.open')}
        title={t('npcDirectory.card.open')}
      >
        <ArrowUpRight className="size-3.5" />
      </Link>
    </article>
  );
}
