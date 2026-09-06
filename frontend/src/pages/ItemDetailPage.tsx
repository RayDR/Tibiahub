import { useEffect, useMemo, useState } from 'react';
import { Coins, Gem, Loader2, PackageOpen, Shield, ShoppingBag, Swords } from 'lucide-react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from '../components/ImageWithFallback';
import {
  KnowledgeBackLink,
  KnowledgeBadge,
  KnowledgeEmpty,
  KnowledgeFact,
  KnowledgeFacts,
  KnowledgeHero,
  KnowledgeSection,
} from '../components/knowledge/KnowledgeDetail';
import { Page } from '../components/ui';
import { itemsApi } from '../services/api';
import { activityApi } from '../services/activity';
import { useAuth } from '../context/AuthContext';
import type { ItemDetail, ItemRelatedEntity } from '../types';
import { availableItemMediaUrl } from '../utils/entityMedia';
import { SuggestCorrectionLink } from '../components/feedback/GitHubFeedbackLink';
import { useSeoMetadata } from '../utils/seo';

const normalizedName = (value: string) => value.trim().toLocaleLowerCase().replace(/\s+/g, ' ');

function displayRecord(value: Record<string, unknown>): string {
  const name = value.name ?? value.npc ?? value.item ?? value.value;
  return typeof name === 'string'
    ? name
    : Object.values(value)
        .filter((entry) => typeof entry === 'string' || typeof entry === 'number')
        .join(' · ');
}

function relatedPath(entity: ItemRelatedEntity): string {
  const segment = entity.kind === 'quest' ? 'quests' : entity.kind === 'npc' ? 'npcs' : 'locations';
  return `/${segment}/${entity.slug}`;
}

function AttributeList({ values, yes }: { values: Record<string, unknown>; yes: string }) {
  const entries = Object.entries(values || {}).filter(([, value]) => value !== null && value !== undefined && value !== false && value !== '');
  return <dl className="grid gap-2 sm:grid-cols-2">{entries.map(([key, value]) => (
    <div key={key} className="flex justify-between gap-4 rounded-lg bg-surface-base/60 px-3 py-2 text-sm">
      <dt className="capitalize text-content-secondary">{key.split('_').join(' ')}</dt>
      <dd className="text-right font-medium text-content-primary">{value === true ? yes : Array.isArray(value) ? value.join(', ') : String(value)}</dd>
    </div>
  ))}</dl>;
}

export default function ItemDetailPage() {
  const { identifier } = useParams<{ identifier: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const canonicalItemPath = item ? `/items/${item.slug || item.normalized_name.split(' ').join('-')}` : '';
  const itemMediaUrl = availableItemMediaUrl(item?.media);

  useSeoMetadata(item ? {
    title: `${item.item_name} — Tibia item`,
    description: item.description || `Attributes, creature drops, hunt zones and uses for ${item.item_name}.`,
    canonicalPath: canonicalItemPath,
    type: 'article',
    image: itemMediaUrl,
    breadcrumbs: [{ name: 'Home', path: '/' }, { name: 'Cyclopedia', path: '/cyclopedia' }, { name: item.item_name, path: canonicalItemPath }],
  } : null);

  useEffect(() => {
    if (!identifier) return undefined;
    const controller = new AbortController();
    setLoading(true);
    void itemsApi.getByIdentifier(identifier, controller.signal).then((result) => {
      setItem(result);
      setError(false);
      if (isAuthenticated && result.id) {
        void activityApi.record({
          activity_type: 'view_item',
          entity_type: 'items',
          entity_id: String(result.id),
          metadata: {
            name: result.item_name,
            slug: result.slug,
            normalized_name: result.normalized_name,
            media_url: availableItemMediaUrl(result.media),
          },
        }).catch(() => {
          // Visit history is non-blocking.
        });
      }
      if (result.slug && result.slug !== identifier) navigate(`/items/${result.slug}`, { replace: true, state: location.state });
    }).catch(() => setError(true)).finally(() => setLoading(false));
    return () => controller.abort();
  }, [identifier, isAuthenticated, location.state, navigate]);

  const relatedByName = useMemo(() => new Map(
    (item?.related_entities || []).map((entity) => [normalizedName(entity.name), entity]),
  ), [item]);

  if (loading) return <Page><div className="flex min-h-[24rem] items-center justify-center text-primary"><Loader2 className="animate-spin" size={42} /></div></Page>;
  if (!item || error) return <Page><div className="rounded-2xl border border-danger/25 bg-danger-subtle p-6 text-danger"><h1 className="text-xl font-bold">{t('itemDetail.unavailable')}</h1><p className="mt-2">{t('itemDetail.notFound')}</p></div></Page>;

  const back = (location.state as { from?: string } | null)?.from || '/cyclopedia?tab=loot';
  const attributes = { ...item.attributes, ...item.resistances, ...item.bonuses };
  const attributeCount = Object.values(attributes).filter((value) => value !== null && value !== undefined && value !== false && value !== '').length;
  const usefulFacts = [
    item.weight != null ? <KnowledgeFact key="weight" label={t('itemDetail.weight')} value={`${item.weight} oz`} /> : null,
    item.value != null ? <KnowledgeFact key="value" label={t('itemDetail.value')} value={`${item.value.toLocaleString()} gp`} /> : null,
    item.level_requirement != null ? <KnowledgeFact key="level" label={t('itemDetail.level')} value={item.level_requirement} /> : null,
    item.vocation_requirements.length ? <KnowledgeFact key="vocations" label={t('itemDetail.vocations')} value={item.vocation_requirements.join(', ')} /> : null,
  ].filter(Boolean);
  const combatFacts = [
    item.attack != null ? <KnowledgeFact key="attack" label={t('itemDetail.attack')} value={item.attack} /> : null,
    item.defense != null ? <KnowledgeFact key="defense" label={t('itemDetail.defense')} value={item.defense} /> : null,
    item.armor != null ? <KnowledgeFact key="armor" label={t('itemDetail.armor')} value={item.armor} /> : null,
    item.range != null ? <KnowledgeFact key="range" label={t('itemDetail.range')} value={item.range} /> : null,
  ].filter(Boolean);
  const hasEquipmentDetails = combatFacts.length > 0 || item.slots.length > 0 || item.imbuement_slots != null;
  const hasTrade = item.buy_from.length > 0 || item.sell_to.length > 0;
  const linkedValue = (name: string) => {
    const target = relatedByName.get(normalizedName(name));
    return target ? <Link className="font-semibold text-primary hover:underline" to={relatedPath(target)}>{name}</Link> : name;
  };

  return <Page>
    <KnowledgeBackLink to={back}>{t('itemDetail.back')}</KnowledgeBackLink>
    <KnowledgeHero
      eyebrow={t('itemDetail.eyebrow')}
      title={item.item_name}
      description={item.description || item.notes || undefined}
      media={<div className="aspect-square rounded-2xl border border-line bg-surface-base/70 p-6"><ImageWithFallback src={itemMediaUrl} alt={item.item_name} className="h-full w-full object-contain [image-rendering:pixelated]" containerClassName="h-full w-full" fallbackLabel={item.item_name} /></div>}
      badges={<>{[item.category, item.item_type, item.item_class, item.rarity].filter(Boolean).map((value) => <KnowledgeBadge key={value} tone="primary">{value}</KnowledgeBadge>)}</>}
    />

    {usefulFacts.length ? <div className="mt-6"><KnowledgeFacts>{usefulFacts}</KnowledgeFacts></div> : null}

    {(hasEquipmentDetails || attributeCount > 0) ? <div className="mt-8 grid gap-6 lg:grid-cols-2">
      {hasEquipmentDetails ? <KnowledgeSection title={t('itemDetail.combat')} icon={<Swords size={20} />}>
        {combatFacts.length ? <KnowledgeFacts>{combatFacts}</KnowledgeFacts> : null}
        {(item.slots.length || item.imbuement_slots != null) ? <div className="mt-4 flex flex-wrap gap-2">{item.slots.map((slot) => <KnowledgeBadge key={slot}>{slot}</KnowledgeBadge>)}{item.imbuement_slots != null ? <KnowledgeBadge>{t('itemDetail.imbuements')}: {item.imbuement_slots}</KnowledgeBadge> : null}</div> : null}
      </KnowledgeSection> : null}
      {attributeCount ? <KnowledgeSection title={t('itemDetail.attributes')} icon={<Shield size={20} />}><AttributeList values={attributes} yes={t('common.yes')} /></KnowledgeSection> : null}
    </div> : null}

    <div className="mt-6 grid gap-6 lg:grid-cols-2">
      <KnowledgeSection title={t('itemDetail.acquisition')} icon={<Gem size={20} />} className={hasTrade ? '' : 'lg:col-span-2'}>
        {item.drops.length ? <div className="grid gap-3 sm:grid-cols-2">{item.drops.map((drop) => {
          const amount = drop.min_amount && drop.max_amount && (drop.min_amount > 1 || drop.max_amount > 1)
            ? (drop.min_amount === drop.max_amount ? String(drop.min_amount) : `${drop.min_amount}–${drop.max_amount}`)
            : null;
          const creatureRoute = drop.creature_slug || drop.creature_id;
          return <article key={`${drop.creature_id}-${drop.creature_name}`} className="rounded-xl border border-line bg-surface-base/60 p-3">
            <div className="flex min-w-0 items-center gap-3">
              {drop.creature_id ? <img src={`/api/v1/creatures/${drop.creature_id}/image?placeholder=false`} alt="" className="size-14 shrink-0 object-contain [image-rendering:pixelated]" loading="lazy" /> : null}
              <div className="min-w-0"><div className="flex flex-wrap items-center gap-2">{creatureRoute ? <Link className="font-semibold text-primary hover:underline" to={`/creatures/${creatureRoute}`}>{drop.creature_name}</Link> : <span className="font-semibold text-content-primary">{drop.creature_name}</span>}<KnowledgeBadge tone={drop.is_boss ? 'danger' : 'neutral'}>{t(drop.is_boss ? 'itemDetail.boss' : 'itemDetail.creature')}</KnowledgeBadge></div>
                <div className="mt-2 flex flex-wrap gap-2">{drop.chance != null ? <KnowledgeBadge tone="primary">{t('itemDetail.chance', { value: drop.chance })}</KnowledgeBadge> : null}{drop.rarity ? <KnowledgeBadge>{t('itemDetail.rarity', { value: drop.rarity })}</KnowledgeBadge> : null}{amount ? <KnowledgeBadge>{t('itemDetail.amount', { value: amount })}</KnowledgeBadge> : null}</div>
              </div>
            </div>
            {drop.hunt_zones.length ? <div className="mt-3 flex flex-wrap gap-2">{drop.hunt_zones.map((zone) => <Link key={zone.id} to={`/hunt-zones/${zone.slug || zone.id}`} className="inline-flex min-h-8 items-center rounded-full border border-line px-3 py-1 text-xs text-content-secondary hover:border-primary hover:text-primary">{zone.name}</Link>)}</div> : null}
          </article>;
        })}</div> : <KnowledgeEmpty>{t('itemDetail.noDrops')}</KnowledgeEmpty>}
      </KnowledgeSection>

      {hasTrade ? <KnowledgeSection title={t('itemDetail.trade')} icon={<ShoppingBag size={20} />}><div className="grid gap-5 sm:grid-cols-2">
        {[{ title: t('itemDetail.buyFrom'), values: item.buy_from }, { title: t('itemDetail.sellTo'), values: item.sell_to }].map((group) => group.values.length ? <div key={group.title}><h3 className="mb-2 text-sm font-semibold text-content-primary">{group.title}</h3><ul className="space-y-2 text-sm text-content-secondary">{group.values.map((value, index) => { const label = displayRecord(value); return <li key={`${label}-${index}`} className="rounded-lg bg-surface-base/60 px-3 py-2">{linkedValue(label)}</li>; })}</ul></div> : null)}
      </div></KnowledgeSection> : null}

      {(item.required_for.length || item.rewards_from.length) ? <KnowledgeSection title={t('itemDetail.usedFor')} icon={<PackageOpen size={20} />}><div className="grid gap-5 sm:grid-cols-2">
        {[{ title: t('itemDetail.requiredFor'), values: item.required_for }, { title: t('itemDetail.rewardsFrom'), values: item.rewards_from }].map((group) => group.values.length ? <div key={group.title}><h3 className="mb-2 text-sm font-semibold text-content-primary">{group.title}</h3><ul className="space-y-2 text-sm text-content-secondary">{group.values.map((value) => <li key={value} className="rounded-lg bg-surface-base/60 px-3 py-2">{linkedValue(value)}</li>)}</ul></div> : null)}
      </div></KnowledgeSection> : null}

      {item.notes && item.notes !== item.description ? <KnowledgeSection title={t('itemDetail.notes')} icon={<PackageOpen size={20} />}><p className="whitespace-pre-line leading-7 text-content-secondary">{item.notes}</p></KnowledgeSection> : null}

      {(item.last_synced_at || item.source_url) ? <KnowledgeSection title={t('itemDetail.provenance')} icon={<Coins size={20} />}><div className="space-y-2 text-sm text-content-secondary">{item.last_synced_at ? <p>{t('itemDetail.updated', { date: new Date(item.last_synced_at).toLocaleDateString() })}</p> : null}{item.source_url ? <a href={item.source_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">{t('itemDetail.source')}</a> : null}</div></KnowledgeSection> : null}
    </div>
    <div className="mt-6 flex justify-end"><SuggestCorrectionLink entityType="Item" entityName={item.item_name} /></div>
  </Page>;
}
