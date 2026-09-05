import {
  ArrowUpRight,
  BookOpenCheck,
  Coins,
  Map,
  MapPin,
  UserRound,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { buildMapEntityUrl } from '../services/tibiaMap';
import type { NpcDirectoryItem } from '../types';
import { localNpcMediaUrl } from '../utils/npcCyclopedia';
import { Badge } from './ui';

interface NpcCardProps {
  npc: NpcDirectoryItem;
  linkState?: unknown;
  onNavigate?: () => void;
}

function Fact({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return <span className="inline-flex min-h-7 items-center gap-1.5 text-xs text-content-secondary">{icon}{children}</span>;
}

function knownCount(
  value: number | null | undefined,
  none: string,
  unknown: string,
  count: (value: number) => string,
) {
  if (value == null) return unknown;
  return value === 0 ? none : count(value);
}

function NpcPortrait({ npc }: { npc: NpcDirectoryItem }) {
  const mediaUrl = localNpcMediaUrl(npc.media);
  const [failed, setFailed] = useState(false);

  useEffect(() => setFailed(false), [mediaUrl]);

  return (
    <div className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-xl border border-line bg-primary/10 text-primary">
      {mediaUrl && !failed ? (
        <img
          src={mediaUrl}
          alt=""
          aria-hidden="true"
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="size-full object-contain [image-rendering:pixelated]"
        />
      ) : (
        <UserRound className="size-7" aria-hidden="true" />
      )}
    </div>
  );
}

export default function NpcCard({ npc, linkState, onNavigate }: NpcCardProps) {
  const { t } = useTranslation();
  const detailPath = `/npcs/${npc.canonical_id}`;
  const mapPath = buildMapEntityUrl({
    entityType: 'npc',
    canonicalEntityId: npc.canonical_id,
    name: npc.name,
    slug: npc.slug,
  });

  return (
    <article className="group flex min-h-full flex-col rounded-2xl border border-line bg-surface-base/70 p-4 transition hover:border-primary/40 hover:bg-surface-raised">
      <div className="flex min-w-0 items-start gap-3">
        <NpcPortrait npc={npc} />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-content-muted">{t('npcDirectory.card.eyebrow')}</p>
          <h2 className="truncate text-lg font-bold text-content-primary">{npc.name}</h2>
          {(npc.title || npc.occupation) ? <p className="line-clamp-2 text-sm text-content-secondary">{npc.title || npc.occupation}</p> : null}
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-1.5">
        <Fact icon={<MapPin className="size-3.5 text-primary" />}><span className="line-clamp-1">{npc.location_name || t('npcDirectory.unknown.location')}</span></Fact>
        <Fact icon={<Coins className="size-3.5 text-primary" />}>
          {knownCount(npc.buys_count, t('npcDirectory.none.buys'), t('npcDirectory.unknown.buys'), (count) => t('npcDirectory.count.buys', { count }))}
          <span aria-hidden="true">·</span>
          {knownCount(npc.sells_count, t('npcDirectory.none.sells'), t('npcDirectory.unknown.sells'), (count) => t('npcDirectory.count.sells', { count }))}
        </Fact>
        <Fact icon={<BookOpenCheck className="size-3.5 text-primary" />}>{knownCount(npc.quest_count, t('npcDirectory.none.quests'), t('npcDirectory.unknown.quests'), (count) => t('npcDirectory.count.quests', { count }))}</Fact>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {npc.map_available ? <Badge tone="success"><Map className="size-3" />{t('npcDirectory.card.mapped')}</Badge> : <Badge>{t('npcDirectory.card.mapPending')}</Badge>}
        {npc.destination_count != null && npc.destination_count > 0 ? <Badge tone="info">{t('npcDirectory.count.destinations', { count: npc.destination_count })}</Badge> : null}
      </div>

      <div className="mt-auto flex flex-wrap gap-2 pt-5">
        <Link to={detailPath} state={linkState} onClick={onNavigate} className="app-button-primary app-button-sm flex-1 justify-center">{t('npcDirectory.card.open')}<ArrowUpRight className="size-4" /></Link>
        {npc.map_available ? <Link to={mapPath} state={linkState} onClick={onNavigate} className="app-button-secondary app-button-sm" aria-label={t('npcDirectory.card.openMapFor', { name: npc.name })}><Map className="size-4" /></Link> : null}
      </div>
    </article>
  );
}
