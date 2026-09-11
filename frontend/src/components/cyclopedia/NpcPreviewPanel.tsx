import {
  ArrowRight,
  Banknote,
  BookOpenCheck,
  CircleEllipsis,
  Compass,
  FlaskConical,
  Info,
  Loader2,
  MapPin,
  PackageOpen,
  Route,
  ScrollText,
  Shield,
  ShoppingCart,
  Sparkles,
  Swords,
  UserRound,
  UtensilsCrossed,
} from 'lucide-react';
import { useEffect, useMemo, useState, type ComponentType } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from '../ImageWithFallback';
import LocalizedMapPreview from '../map/LocalizedMapPreview';
import { namedKnowledgeApi } from '../../services/api';
import { buildMapEntityUrl, tibiaMapApi, type WorldMapFloor } from '../../services/tibiaMap';
import type { NpcKnowledgeDetail } from '../../types';
import { localNpcMediaUrl } from '../../utils/npcCyclopedia';

type NpcServiceKind =
  | 'trade'
  | 'potions'
  | 'banking'
  | 'depot'
  | 'travel'
  | 'quests'
  | 'blessings'
  | 'food'
  | 'hunting'
  | 'tasks'
  | 'runes'
  | 'weapons'
  | 'armor'
  | 'ammunition'
  | 'information'
  | 'service';

interface NpcPreviewService {
  kind: NpcServiceKind;
  label: string;
  detail: string;
  tooltip: string;
  Icon: ComponentType<{ className?: string }>;
}

function uniqueNames(values: Array<{ name: string }>, limit: number): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const name = value.name?.trim();
    const key = name.toLowerCase();
    if (!name || seen.has(key)) continue;
    seen.add(key);
    result.push(name);
    if (result.length >= limit) break;
  }
  return result;
}

function listSummary(values: Array<{ name: string }>, limit = 4): string {
  return uniqueNames(values, limit).join(' · ');
}

function buildNpcServices(
  npc: NpcKnowledgeDetail,
  questCount: number,
  t: (key: string, options?: Record<string, unknown>) => string,
): NpcPreviewService[] {
  const services: NpcPreviewService[] = [];
  const seen = new Set<NpcServiceKind>();
  const offerNames = [...npc.buys, ...npc.sells].map((value) => value.name).join(' ');
  const context = `${npc.title || ''} ${npc.occupation || ''} ${offerNames}`.toLowerCase();
  const role = npc.occupation || npc.title || '';

  const add = (
    kind: NpcServiceKind,
    label: string,
    detail: string,
    tooltip: string,
    Icon: NpcPreviewService['Icon'],
  ) => {
    if (seen.has(kind)) return;
    seen.add(kind);
    services.push({ kind, label, detail, tooltip, Icon });
  };

  if (npc.buys.length || npc.sells.length) {
    const parts = [
      npc.buys.length ? t('npcPreview.buyCount', { defaultValue: '{{count}} items bought', count: npc.buys.length }) : '',
      npc.sells.length ? t('npcPreview.sellCount', { defaultValue: '{{count}} items sold', count: npc.sells.length }) : '',
    ].filter(Boolean);
    const examples = listSummary([...npc.sells, ...npc.buys], 3);
    add(
      'trade',
      t('npcDetail.trade'),
      [parts.join(' · '), examples].filter(Boolean).join(' — '),
      t('npcCard.serviceTips.trade', { defaultValue: 'Trades items with players.' }),
      ShoppingCart,
    );
  }

  if (/potion|alchemi|chemist|herbal|vial|flask/.test(context)) {
    add(
      'potions',
      t('npcCard.services.potions', { defaultValue: 'Potions' }),
      role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : t('npcPreview.potionDetail', { defaultValue: 'Potion and alchemy-related offers.' }),
      t('npcCard.serviceTips.potions', { defaultValue: 'Potion or alchemy service indicated by known NPC data.' }),
      FlaskConical,
    );
  }
  if (/bank|banker/.test(context)) {
    add('banking', t('npcCard.services.banking', { defaultValue: 'Banking' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : '', t('npcCard.serviceTips.banking', { defaultValue: 'Banking service indicated by this NPC’s role.' }), Banknote);
  }
  if (/depot/.test(context)) {
    add('depot', t('npcCard.services.depot', { defaultValue: 'Depot' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : '', t('npcCard.serviceTips.depot', { defaultValue: 'Depot-related service indicated by this NPC’s role.' }), PackageOpen);
  }
  if (/bless|priest|temple/.test(context)) {
    add('blessings', t('npcCard.services.blessings', { defaultValue: 'Blessings' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : '', t('npcCard.serviceTips.blessings', { defaultValue: 'Blessing or temple service indicated by this NPC’s role.' }), Sparkles);
  }
  if (/food|cook|baker|tavern|innkeeper|bartender/.test(context)) {
    add('food', t('npcCard.services.food', { defaultValue: 'Food' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : '', t('npcCard.serviceTips.food', { defaultValue: 'Food service indicated by this NPC’s role.' }), UtensilsCrossed);
  }
  if (/hunt|hunter/.test(context)) {
    add('hunting', t('npcCard.services.hunting', { defaultValue: 'Hunting' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : '', t('npcCard.serviceTips.hunting', { defaultValue: 'Hunting-related service indicated by this NPC’s role.' }), Compass);
  }
  if (/task/.test(context)) {
    add('tasks', t('npcCard.services.tasks', { defaultValue: 'Tasks' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : '', t('npcCard.serviceTips.tasks', { defaultValue: 'Task-related service indicated by this NPC’s role.' }), ScrollText);
  }
  if (/rune/.test(context)) {
    add('runes', t('npcCard.services.runes', { defaultValue: 'Runes' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : listSummary([...npc.sells, ...npc.buys], 3), t('npcCard.serviceTips.runes', { defaultValue: 'Rune-related service indicated by known NPC data.' }), Sparkles);
  }
  if (/weapon|blacksmith|smith|sword|axe|club/.test(context)) {
    add('weapons', t('npcCard.services.weapons', { defaultValue: 'Weapons' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : listSummary([...npc.sells, ...npc.buys], 3), t('npcCard.serviceTips.weapons', { defaultValue: 'Weapon-related service indicated by known NPC data.' }), Swords);
  }
  if (/armor|armour|helmet|shield/.test(context)) {
    add('armor', t('npcCard.services.armor', { defaultValue: 'Armor' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : listSummary([...npc.sells, ...npc.buys], 3), t('npcCard.serviceTips.armor', { defaultValue: 'Armor-related service indicated by known NPC data.' }), Shield);
  }
  if (/ammunition|ammo|arrow|bolt|bowyer/.test(context)) {
    add('ammunition', t('npcCard.services.ammunition', { defaultValue: 'Ammunition' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : listSummary([...npc.sells, ...npc.buys], 3), t('npcCard.serviceTips.ammunition', { defaultValue: 'Ammunition-related service indicated by known NPC data.' }), Swords);
  }
  if (/spy|inform|guide|scholar|teacher|trainer|librarian/.test(context)) {
    add('information', t('npcCard.services.information', { defaultValue: 'Information' }), role ? t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }) : '', t('npcCard.serviceTips.information', { defaultValue: 'Information or guidance service indicated by this NPC’s role.' }), Info);
  }

  if (npc.destinations.length) {
    add(
      'travel',
      t('npcCard.services.travel', { defaultValue: 'Travel' }),
      listSummary(npc.destinations, 4) || t('npcDetail.travel'),
      t('npcCard.serviceTips.travel', { defaultValue: 'Offers travel or transportation.' }),
      Route,
    );
  }

  if (questCount > 0) {
    add(
      'quests',
      t('npcCard.services.quests', { defaultValue: 'Quests' }),
      t('npcPreview.questCount', { defaultValue: '{{count}} related quests', count: questCount }),
      t('npcCard.serviceTips.quests', { defaultValue: 'Has known quest relationships.' }),
      BookOpenCheck,
    );
  }

  if (!services.length && role) {
    add(
      'service',
      t('npcCard.services.service', { defaultValue: 'Service' }),
      t('npcPreview.roleDetail', { defaultValue: 'Role: {{role}}', role }),
      t('npcCard.serviceTips.occupation', { defaultValue: 'NPC role or occupation.' }),
      CircleEllipsis,
    );
  }

  return services;
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
        // Coordinates remain useful even when the optional map floor cannot be rendered.
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

    return rows.slice(0, 5);
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
  const locationLabels = uniqueNames((npc.spatial.location_labels || []).map((name) => ({ name })), 4);
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
  const aliases = uniqueNames(
    npc.aliases
      .filter((alias) => alias.trim().toLowerCase() !== npc.name.trim().toLowerCase())
      .map((name) => ({ name })),
    5,
  );
  const externalLabel = npc.external_id
    ? `#${/^\d+$/.test(npc.external_id) ? npc.external_id.padStart(4, '0') : npc.external_id}`
    : null;
  const services = buildNpcServices(npc, questRows.length, t);
  const topServices = services.slice(0, 3);
  const serviceRows = services.filter((service) => service.kind !== 'quests').slice(0, 5);

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
            className="npc-preview-portrait-image [image-rendering:pixelated]"
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

          {topServices.length ? (
            <div className="npc-preview-service-chips" aria-label={t('npcPreview.services', { defaultValue: 'Services' })}>
              {topServices.map(({ kind, label, tooltip, Icon }) => (
                <span
                  key={kind}
                  className="npc-preview-service-chip"
                  data-service={kind}
                  title={tooltip}
                >
                  <Icon className="size-3.5 shrink-0" />
                  {label}
                </span>
              ))}
            </div>
          ) : null}

          <div className="npc-preview-inline-location">
            <MapPin className="size-4 shrink-0" />
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

      {serviceRows.length ? (
        <section className="npc-preview-section npc-preview-services">
          <h3 className="npc-preview-section-title">
            <PackageOpen className="size-4" />
            {t('npcPreview.services', { defaultValue: 'Services' })}
          </h3>
          <div className="npc-preview-service-list">
            {serviceRows.map(({ kind, label, detail, tooltip, Icon }) => (
              <div key={kind} className="npc-preview-service-row" data-service={kind} title={tooltip}>
                <span className="npc-preview-service-icon"><Icon className="size-5" /></span>
                <div className="min-w-0 flex-1">
                  <strong>{label}</strong>
                  {detail ? <p>{detail}</p> : null}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="npc-preview-section npc-preview-location-section">
        <h3 className="npc-preview-section-title">
          <MapPin className="size-4" />
          {t('namedKnowledge.location')}
        </h3>

        <div className="npc-preview-location-grid">
          <div className="npc-preview-location-copy">
            <div className="npc-preview-location-name">
              <MapPin className="size-6 shrink-0" />
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
            <BookOpenCheck className="size-4" />
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
          <h3 className="npc-preview-section-title">
            <UserRound className="size-4" />
            {t('npcDetail.aliases')}
          </h3>
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
          <UserRound className="size-4" />
          {t('npcDetail.overview')}
          <ArrowRight className="size-4" />
        </Link>
      </div>
    </article>
  );
}
