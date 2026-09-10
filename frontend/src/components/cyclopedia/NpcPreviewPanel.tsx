import { ArrowRight, BookOpenCheck, Coins, Loader2, MapPin, PackageOpen, Route, UserRound } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from '../ImageWithFallback';
import LocalizedMapPreview from '../map/LocalizedMapPreview';
import { namedKnowledgeApi } from '../../services/api';
import { buildMapEntityUrl, tibiaMapApi, type WorldMapFloor } from '../../services/tibiaMap';
import type { NpcKnowledgeDetail, NpcNamedReference } from '../../types';
import { localNpcMediaUrl } from '../../utils/npcCyclopedia';

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

function summarizeReferences(values: NpcNamedReference[], limit = 3): string {
  return uniqueNames(values, limit).join(' · ');
}

export default function NpcPreviewPanel({ identifier }: { identifier: string }) {
  const { t } = useTranslation();
  const location = useLocation();
  const [npc, setNpc] = useState<NpcKnowledgeDetail | null>(null);
  const [worldMap, setWorldMap] = useState<WorldMapFloor | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setNpc(null);
    setWorldMap(null);
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

  const mapFloorNumber = npc?.spatial.geometry_status === 'mapped' && npc.spatial.z != null
    ? npc.spatial.z
    : null;

  useEffect(() => {
    const controller = new AbortController();
    setWorldMap(null);

    if (mapFloorNumber == null) return () => controller.abort();

    void tibiaMapApi
      .bootstrap(mapFloorNumber, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setWorldMap(result.world_map);
      })
      .catch(() => {
        // The verified coordinates remain useful when the optional floor preview is unavailable.
      });

    return () => controller.abort();
  }, [mapFloorNumber, npc?.canonical_id]);

  const questRows = useMemo(() => {
    if (!npc) return [];

    const rows: Array<{ key: string; name: string; detail: string; to?: string }> = [];
    const seen = new Set<string>();

    npc.relationships
      .filter((relationship) => relationship.target_type === 'quest')
      .forEach((relationship) => {
        const normalized = relationship.target_name.trim().toLowerCase();
        if (!normalized || seen.has(normalized)) return;
        seen.add(normalized);
        rows.push({
          key: relationship.canonical_id,
          name: relationship.target_name,
          detail: t(`npcDetail.questSemantics.${relationship.relationship_type}`, {
            defaultValue: t('npcDetail.questSemantics.related'),
          }),
          to: relationship.resolution_state === 'resolved' && relationship.target_slug
            ? `/quests/${relationship.target_slug}`
            : undefined,
        });
      });

    npc.related_quests.forEach((quest, index) => {
      const normalized = quest.name.trim().toLowerCase();
      if (!normalized || seen.has(normalized)) return;
      seen.add(normalized);
      rows.push({
        key: quest.canonical_id || `${quest.name}:${index}`,
        name: quest.name,
        detail: t('npcDetail.questSemantics.related'),
        to: quest.navigation_url || (quest.resolution_state === 'resolved' && quest.slug ? `/quests/${quest.slug}` : undefined),
      });
    });

    return rows.slice(0, 4);
  }, [npc, t]);

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
        floor: npc.spatial.z,
      })
    : null;
  const aliases = npc.aliases.slice(0, 5);
  const externalLabel = npc.external_id
    ? `#${/^\d+$/.test(npc.external_id) ? npc.external_id.padStart(4, '0') : npc.external_id}`
    : null;

  const serviceChips: Array<{ key: string; label: string; tone: 'success' | 'info' | 'warning' | 'neutral' }> = [];
  if (npc.buys.length || npc.sells.length) serviceChips.push({ key: 'trade', label: t('npcDetail.trade'), tone: 'success' });
  if (npc.destinations.length) serviceChips.push({ key: 'travel', label: t('npcDetail.travel'), tone: 'info' });
  if (questRows.length) serviceChips.push({ key: 'quests', label: t('npcDetail.quests'), tone: 'warning' });
  if (!serviceChips.length && npc.occupation) serviceChips.push({ key: 'occupation', label: npc.occupation, tone: 'neutral' });

  const serviceRows = [
    npc.buys.length ? {
      key: 'buys',
      icon: <PackageOpen className="size-4" />,
      label: t('npcDetail.buys'),
      detail: summarizeReferences(npc.buys) || t('npcDetail.buysNone'),
      count: npc.buys.length,
    } : null,
    npc.sells.length ? {
      key: 'sells',
      icon: <Coins className="size-4" />,
      label: t('npcDetail.sells'),
      detail: summarizeReferences(npc.sells) || t('npcDetail.sellsNone'),
      count: npc.sells.length,
    } : null,
    npc.destinations.length ? {
      key: 'travel',
      icon: <Route className="size-4" />,
      label: t('npcDetail.travel'),
      detail: summarizeReferences(npc.destinations) || t('npcDetail.travelNone'),
      count: npc.destinations.length,
    } : null,
  ].filter((row): row is NonNullable<typeof row> => Boolean(row));

  const mapSpatial = worldMap && mapped && npc.spatial.x != null && npc.spatial.y != null
    ? {
        geometry_status: 'mapped' as const,
        geometry_source: npc.spatial.geometry_source,
        x: npc.spatial.x,
        y: npc.spatial.y,
        z: npc.spatial.z,
        bounds: npc.spatial.bounds,
        world_map: worldMap,
      }
    : null;

  const coordinates = mapped && npc.spatial.x != null && npc.spatial.y != null
    ? `(${npc.spatial.x}, ${npc.spatial.y}${npc.spatial.z != null ? `, ${npc.spatial.z}` : ''})`
    : null;

  return (
    <article className="creature-preview-panel npc-preview-panel" data-npc-preview-panel>
      <section className="npc-preview-hero">
        <div className="npc-preview-portrait">
          <ImageWithFallback
            src={mediaUrl}
            alt={npc.name}
            className="size-full object-contain [image-rendering:pixelated]"
            containerClassName="size-full"
            fallbackKind="npc"
            fallbackLabel={npc.name}
          />
        </div>

        <div className="npc-preview-hero-copy">
          <div className="npc-preview-title-row">
            <h2 className="npc-preview-name">{npc.name}</h2>
            {externalLabel ? <span className="npc-preview-id">{externalLabel}</span> : null}
          </div>

          {serviceChips.length ? (
            <div className="npc-preview-service-chips">
              {serviceChips.slice(0, 3).map((service) => (
                <span key={service.key} className="npc-preview-service-chip" data-tone={service.tone}>{service.label}</span>
              ))}
            </div>
          ) : null}

          <div className="npc-preview-inline-location">
            <MapPin className="size-4 shrink-0 text-primary" />
            <strong>{locationName || t('npcDetail.unknownLocation')}</strong>
            {coordinates ? <span>{coordinates}</span> : null}
            {mapPath ? (
              <Link to={mapPath} className="npc-preview-map-link">
                {t('npcDetail.openMap')} <ArrowRight className="size-3.5" />
              </Link>
            ) : null}
          </div>

          {npc.description ? <p className="npc-preview-description">{npc.description}</p> : null}
        </div>
      </section>

      <section className="npc-preview-section npc-preview-services">
        <h3 className="npc-preview-section-title">
          <PackageOpen className="size-4 text-primary" />
          {t('npcPreview.services', { defaultValue: 'Services' })}
        </h3>

        {serviceRows.length ? (
          <div className="npc-preview-service-list">
            {serviceRows.map((service) => (
              <div key={service.key} className="npc-preview-service-row">
                <span className="npc-preview-service-icon">{service.icon}</span>
                <div className="min-w-0 flex-1">
                  <div className="npc-preview-service-heading">
                    <strong>{service.label}</strong>
                    <span>{service.count}</span>
                  </div>
                  <p>{service.detail}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="npc-preview-service-row npc-preview-service-row--muted">
            <span className="npc-preview-service-icon"><UserRound className="size-4" /></span>
            <div className="min-w-0 flex-1">
              <strong>{npc.occupation || npc.title || t('npcDetail.overview')}</strong>
              <p>{t('npcDetail.tradeUnknown')}</p>
            </div>
          </div>
        )}
      </section>

      <section className="npc-preview-section npc-preview-location-section">
        <h3 className="npc-preview-section-title">
          <MapPin className="size-4 text-primary" />
          {t('namedKnowledge.location')}
        </h3>

        <div className="npc-preview-location-grid">
          <div className="npc-preview-location-copy">
            <div className="npc-preview-location-name">
              <MapPin className="size-5 shrink-0 text-primary" />
              <div className="min-w-0">
                <strong>{locationName || t('npcDetail.unknownLocation')}</strong>
                {locationLabels.length > 1 ? <span>{locationLabels.slice(1).join(' · ')}</span> : null}
                {coordinates ? <span>{coordinates}</span> : null}
              </div>
            </div>
          </div>

          {mapPath ? (
            <Link to={mapPath} className="npc-preview-map-thumb" aria-label={t('npcDetail.openMap')}>
              {mapSpatial ? (
                <LocalizedMapPreview
                  spatial={mapSpatial}
                  label={t('npcDirectory.card.openMapFor', { name: npc.name })}
                  className="absolute inset-0 size-full"
                />
              ) : (
                <div className="grid size-full place-items-center bg-primary/10 text-primary">
                  <MapPin className="size-7" />
                </div>
              )}
              <span className="npc-preview-map-thumb-open"><ArrowRight className="size-3.5" /></span>
            </Link>
          ) : null}
        </div>
      </section>

      {questRows.length ? (
        <section className="npc-preview-section npc-preview-quests">
          <h3 className="npc-preview-section-title">
            <BookOpenCheck className="size-4 text-primary" />
            {t('npcDetail.quests')} <span className="npc-preview-section-count">({questRows.length})</span>
          </h3>
          <div className="npc-preview-quest-list">
            {questRows.map((quest) => {
              const content = (
                <>
                  <BookOpenCheck className="size-4 shrink-0 text-primary" />
                  <span className="min-w-0 flex-1">
                    <strong>{quest.name}</strong>
                    <small>{quest.detail}</small>
                  </span>
                  <ArrowRight className="size-3.5 shrink-0 text-content-muted" />
                </>
              );
              return quest.to ? (
                <Link key={quest.key} to={quest.to} className="npc-preview-quest-row">{content}</Link>
              ) : (
                <div key={quest.key} className="npc-preview-quest-row">{content}</div>
              );
            })}
          </div>
        </section>
      ) : null}

      {aliases.length ? (
        <section className="npc-preview-section npc-preview-aliases">
          <h3 className="npc-preview-section-title"><UserRound className="size-4 text-primary" />{t('npcDetail.aliases')}</h3>
          <div className="npc-preview-alias-list">
            {aliases.map((alias) => <span key={alias}>{alias}</span>)}
          </div>
        </section>
      ) : null}

      <div className="npc-preview-actions">
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
