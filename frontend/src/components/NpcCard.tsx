import { UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import type { NpcDirectoryItem } from '../types';
import { localNpcMediaUrl } from '../utils/npcCyclopedia';
import './NpcCard.css';

interface NpcCardProps {
  npc: NpcDirectoryItem;
  linkState?: unknown;
  onNavigate?: () => void;
}

function NpcPortrait({ npc }: { npc: NpcDirectoryItem }) {
  const mediaUrl = localNpcMediaUrl(npc.media);
  const [failed, setFailed] = useState(false);

  useEffect(() => setFailed(false), [mediaUrl]);

  return (
    <span className="grid size-20 shrink-0 place-items-center overflow-hidden rounded-xl bg-primary/[0.07] text-primary">
      {mediaUrl && !failed ? (
        <img
          src={mediaUrl}
          alt=""
          aria-hidden="true"
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="max-h-20 max-w-full object-contain p-1 [image-rendering:pixelated]"
        />
      ) : (
        <UserRound className="size-8" aria-hidden="true" />
      )}
    </span>
  );
}

export default function NpcCard({ npc, linkState, onNavigate }: NpcCardProps) {
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
