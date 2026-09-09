import { ArrowRight, BookOpenCheck, Coins, Loader2, MapPin, PackageOpen, Route, UserRound } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import BrandCategoryFallbackIcon from '../icons/BrandCategoryFallbackIcon';
import { namedKnowledgeApi } from '../../services/api';
import { buildMapEntityUrl } from '../../services/tibiaMap';
import type { NpcKnowledgeDetail, NpcNamedReference } from '../../types';
import { localNpcMediaUrl } from '../../utils/npcCyclopedia';

function referenceLabel(value: NpcNamedReference): string {
  return value.price != null ? `${value.name} · ${value.price} gp` : value.name;
}

function uniqueNames(values: Array<{ name: string }>, limit: number): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const name = value.name?.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    result.push(name);
    if (result.length >= limit) break;
  }
  return result;
}

export default function NpcPreviewPanel({ identifier }: { identifier: string }) {
  const { t } = useTranslation();
  const location = useLocation();
  const [npc, setNpc] = useState<NpcKnowledgeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setNpc(null);
    setLoading(true);
    setError(false);

    void namedKnowledgeApi
      .getNpc(identifier, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setNpc(result);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [identifier]);

  const questNames = useMemo(() => {
    if (!npc) return [];
    const graph = npc.relationships
      .filter((relationship) => relationship.target_type === 'quest')
      .map((relationship) => ({ name: relationship.target_name }));
    return uniqueNames([...graph, ...npc.related_quests], 5);
  }, [npc]);

  if (loading) {
    return (
      <div className="creature-preview-panel npc-preview-panel creature-preview-loading" role="status">
        <Loader2 className="size-6 animate-spin text-primary" />
        <span className="text-sm text-content-muted">{t('common.loading')}</span>
      </div>
    );
  }

  if (!npc || error) {
    return (
      <div className="creature-preview-panel npc-preview-panel p-5 text-sm text-danger">
        {t('namedKnowledge.npcUnavailable')}
      </div>
    );
  }

  const mediaUrl = localNpcMediaUrl(npc.media);
  const npcPath = `/npcs/${npc.canonical_id}`;
  const locationLabels = uniqueNames(
    (npc.spatial.location_labels || []).map((name) => ({ name })),
    4,
  );
  const locationName = npc.location_name || locationLabels[0];
  const mapped = npc.spatial.geometry_status === 'mapped';
  const mapPath = mapped
    ? buildMapEntityUrl({
        canonicalEntityId: npc.canonical_id,
        entityType: 'npc',
        name: npc.name,
        slug: npc.slug,
      })
    : null;
  const aliases = npc.aliases.slice(0, 4);
  const tradeKnown = npc.field_coverage.buys !== 'unknown' || npc.field_coverage.sells !== 'unknown';
  const travelKnown = npc.field_coverage.destinations !== 'unknown';
  const questsKnown = npc.field_coverage.related_quests !== 'unknown' || questNames.length > 0;

  return (
    <article className="creature-preview-panel npc-preview-panel" data-npc-preview-panel>
      <section className="creature-preview-identity npc-preview-identity">
        <div className="creature-preview-sprite npc-preview-sprite">
          {mediaUrl ? (
            <img
              src={mediaUrl}
              alt=""
              aria-hidden="true"
              className="size-full object-contain [image-rendering:pixelated]"
            />
          ) : (
            <BrandCategoryFallbackIcon category="npcs" className="size-20 opacity-85" />
          )}
        </div>
        <div className="min-w-0">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">{t('nav.npcs')}</p>
          <h2 className="creature-preview-name break-words">{npc.name}</h2>
          {npc.title || npc.occupation ? (
            <p className="mt-1 text-sm font-medium text-content-secondary">{npc.title || npc.occupation}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {npc.occupation ? <span className="creature-preview-chip">{npc.occupation}</span> : null}
            {npc.sex ? <span className="creature-preview-chip">{npc.sex}</span> : null}
            {mapped ? <span className="creature-preview-chip">{t('npcDetail.openMap')}</span> : null}
          </div>
          {npc.description ? (
            <p className="mt-3 line-clamp-4 text-sm leading-6 text-content-secondary">{npc.description}</p>
          ) : null}
        </div>
      </section>

      <section className="creature-preview-stats" aria-label={t('npcDetail.overview')}>
        <PreviewStat icon={<PackageOpen className="size-3.5" />} label={t('npcDetail.buys')} value={String(npc.buys.length)} />
        <PreviewStat icon={<Coins className="size-3.5" />} label={t('npcDetail.sells')} value={String(npc.sells.length)} />
        <PreviewStat icon={<BookOpenCheck className="size-3.5" />} label={t('npcDetail.quests')} value={String(questNames.length)} />
        <PreviewStat icon={<Route className="size-3.5" />} label={t('npcDetail.travel')} value={String(npc.destinations.length)} />
      </section>

      <section className="npc-preview-location">
        <h3 className="creature-preview-section-title"><MapPin className="size-4 text-primary" />{t('namedKnowledge.location')}</h3>
        <div className="mt-2 rounded-lg border border-line/60 bg-surface-base/35 p-3">
          <p className="font-semibold text-content-primary">{locationName || t('npcDetail.unknownLocation')}</p>
          {locationLabels.length > 1 ? <p className="mt-1 text-xs text-content-muted">{locationLabels.join(' · ')}</p> : null}
          {mapped && npc.spatial.x != null && npc.spatial.y != null ? (
            <p className="mt-2 text-[11px] text-content-muted">
              X {npc.spatial.x} · Y {npc.spatial.y}{npc.spatial.z != null ? ` · Z ${npc.spatial.z}` : ''}
            </p>
          ) : null}
        </div>
      </section>

      {tradeKnown ? (
        <section className="creature-preview-columns npc-preview-columns">
          <NpcReferenceColumn title={t('npcDetail.buys')} values={npc.buys.slice(0, 4)} />
          <NpcReferenceColumn title={t('npcDetail.sells')} values={npc.sells.slice(0, 4)} />
        </section>
      ) : null}

      {(questsKnown || travelKnown) ? (
        <section className="creature-preview-columns npc-preview-columns">
          <div className="min-w-0">
            <h3 className="creature-preview-section-title"><BookOpenCheck className="size-4 text-primary" />{t('npcDetail.quests')}</h3>
            {questNames.length ? (
              <div className="creature-preview-list">
                {questNames.map((name) => <div key={name} className="creature-preview-row"><span className="truncate">{name}</span></div>)}
              </div>
            ) : <p className="mt-2 text-xs text-content-muted">{t('npcDetail.questsNone')}</p>}
          </div>
          <div className="min-w-0">
            <h3 className="creature-preview-section-title"><Route className="size-4 text-primary" />{t('npcDetail.travel')}</h3>
            {npc.destinations.length ? (
              <div className="creature-preview-list">
                {npc.destinations.slice(0, 5).map((destination, index) => (
                  <div key={`${destination.name}-${index}`} className="creature-preview-row"><span className="truncate">{referenceLabel(destination)}</span></div>
                ))}
              </div>
            ) : <p className="mt-2 text-xs text-content-muted">{t('npcDetail.travelNone')}</p>}
          </div>
        </section>
      ) : null}

      {aliases.length ? (
        <section className="npc-preview-aliases">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-content-muted">{t('npcDetail.aliases')}</span>
          <div className="mt-2 flex flex-wrap gap-1.5">{aliases.map((alias) => <span key={alias} className="creature-preview-chip">{alias}</span>)}</div>
        </section>
      ) : null}

      <div className="npc-preview-actions">
        {mapPath ? (
          <Link to={mapPath} className="app-button-secondary app-button-sm justify-center">
            <MapPin className="size-4" />{t('npcDetail.openMap')}
          </Link>
        ) : null}
        <Link
          to={npcPath}
          state={{ from: `${location.pathname}${location.search}` }}
          className="creature-preview-full-link"
        >
          <UserRound className="size-4" />{t('npcDetail.overview')}<ArrowRight className="size-4" />
        </Link>
      </div>
    </article>
  );
}

function PreviewStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="creature-preview-stat">
      <span className="flex items-center gap-1.5">{icon}{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function NpcReferenceColumn({ title, values }: { title: string; values: NpcNamedReference[] }) {
  return (
    <div className="min-w-0">
      <h3 className="creature-preview-section-title"><PackageOpen className="size-4 text-primary" />{title}</h3>
      {values.length ? (
        <div className="creature-preview-list">
          {values.map((value, index) => (
            <div key={`${value.name}-${index}`} className="creature-preview-row"><span className="truncate">{referenceLabel(value)}</span></div>
          ))}
        </div>
      ) : <p className="mt-2 text-xs text-content-muted">—</p>}
    </div>
  );
}
