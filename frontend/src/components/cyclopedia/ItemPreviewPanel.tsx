import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  ArrowRight,
  BadgeDollarSign,
  Coins,
  Gem,
  Info,
  Layers3,
  Loader2,
  PackageOpen,
  Shield,
  ShoppingBag,
  Sparkles,
  Swords,
  Weight,
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from '../ImageWithFallback';
import { itemsApi } from '../../services/api';
import type { ItemDetail, ItemDropCreature } from '../../types';
import { availableItemMediaUrl } from '../../utils/entityMedia';

function displayRecord(value: Record<string, unknown>): string {
  const candidate = value.name ?? value.npc ?? value.item ?? value.value;
  if (typeof candidate === 'string') return candidate;
  return Object.values(value)
    .filter((entry) => typeof entry === 'string' || typeof entry === 'number')
    .join(' · ');
}

function displayNumber(value: number | null | undefined, suffix = ''): string {
  if (value == null) return '—';
  return `${value.toLocaleString()}${suffix}`;
}

function recordPrice(value: Record<string, unknown>): number | null {
  for (const key of ['price', 'value', 'cost']) {
    const candidate = value[key];
    if (typeof candidate === 'number' && Number.isFinite(candidate)) return candidate;
    if (typeof candidate === 'string') {
      const parsed = Number(candidate.replace(/[^0-9.-]/g, ''));
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
}

function formatGold(value: number | null | undefined): string {
  if (value == null) return '—';
  if (Math.abs(value) >= 1000) {
    const compact = value / 1000;
    return `~ ${compact.toLocaleString(undefined, { maximumFractionDigits: compact >= 100 ? 0 : 1 })}k gp`;
  }
  return `~ ${value.toLocaleString()} gp`;
}

function priceRange(rows: Record<string, unknown>[]): string {
  const prices = rows
    .map(recordPrice)
    .filter((value): value is number => value != null)
    .sort((a, b) => a - b);
  if (!prices.length) return '—';
  if (prices.length === 1 || prices[0] === prices[prices.length - 1]) return formatGold(prices[0]);
  return `${formatGold(prices[0]).replace(/^~ /, '')} – ${formatGold(prices[prices.length - 1]).replace(/^~ /, '')}`;
}

function rarityKey(value?: string | null): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-');
}

function dropPath(drop: ItemDropCreature): string | null {
  if (drop.creature_slug) return `/creatures/${drop.creature_slug}`;
  if (drop.creature_id != null) return `/creatures/${drop.creature_id}`;
  return null;
}

export default function ItemPreviewPanel({ identifier }: { identifier: string }) {
  const { t } = useTranslation();
  const location = useLocation();
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    setItem(null);

    void itemsApi
      .getByIdentifier(identifier, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setItem(result);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [identifier]);

  const drops = useMemo(() => {
    if (!item) return [];
    const seen = new Set<string>();
    return item.drops.filter((drop) => {
      const key = `${drop.creature_id ?? ''}:${drop.creature_name.trim().toLowerCase()}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [item]);

  const bestDrop = useMemo(() => {
    if (!drops.length) return null;
    return [...drops].sort((a, b) => (b.chance ?? -1) - (a.chance ?? -1))[0] || null;
  }, [drops]);

  if (loading) {
    return (
      <div className="creature-preview-panel loot-preview-panel creature-preview-loading" role="status">
        <Loader2 className="size-6 animate-spin text-primary" />
        <span className="text-sm text-content-muted">{t('common.loading')}</span>
      </div>
    );
  }

  if (!item || error) {
    return (
      <div className="creature-preview-panel loot-preview-panel p-5 text-sm text-danger">
        {t('itemDetail.unavailable')}
      </div>
    );
  }

  const itemPath = `/items/${item.slug || item.normalized_name.split(' ').join('-')}`;
  const itemMediaUrl = availableItemMediaUrl(item.media);
  const rarity = item.rarity || drops.find((drop) => drop.rarity)?.rarity || null;
  const identityBadges = [item.item_type, item.item_class].filter(
    (value): value is string => Boolean(value),
  );
  const combatFacts = [
    item.attack != null ? `${t('itemDetail.attack')}: ${item.attack}` : null,
    item.defense != null ? `${t('itemDetail.defense')}: ${item.defense}` : null,
    item.armor != null ? `${t('itemDetail.armor')}: ${item.armor}` : null,
    item.range != null ? `${t('itemDetail.range')}: ${item.range}` : null,
  ].filter((value): value is string => Boolean(value));
  const tradeRows = [
    ...item.buy_from.slice(0, 2).map((row) => ({ label: t('itemDetail.buyFrom'), value: displayRecord(row) })),
    ...item.sell_to.slice(0, 2).map((row) => ({ label: t('itemDetail.sellTo'), value: displayRecord(row) })),
  ];
  const relatedUsage = [...item.required_for.slice(0, 3), ...item.rewards_from.slice(0, 3)];
  const primarySlot = item.slots[0] || item.item_type || '—';
  const bestDropZone = bestDrop?.hunt_zones?.[0]?.name || null;

  return (
    <article className="creature-preview-panel loot-preview-panel" data-item-preview-panel>
      <section className="loot-preview-hero">
        <div className="loot-preview-art">
          <ImageWithFallback
            src={itemMediaUrl}
            alt={item.item_name}
            className="size-full object-contain [image-rendering:pixelated]"
            containerClassName="size-full"
            fallbackKind="item"
            fallbackLabel={item.item_name}
          />
        </div>

        <div className="loot-preview-hero-copy">
          <div className="loot-preview-title-row">
            <div className="min-w-0">
              <h2 className="loot-preview-name">{item.item_name}</h2>
              {rarity ? (
                <span className="loot-rarity-chip loot-rarity-chip--preview" data-rarity={rarityKey(rarity)}>
                  {rarity}
                </span>
              ) : null}
            </div>
            {item.game_item_id != null ? (
              <span className="loot-preview-id">#{item.game_item_id}</span>
            ) : null}
          </div>

          {(identityBadges.length > 0 || combatFacts.length > 0) ? (
            <div className="loot-preview-tags">
              {identityBadges.slice(0, 2).map((badge) => (
                <span key={badge} className="loot-preview-tag"><Layers3 className="size-3.5" />{badge}</span>
              ))}
              {combatFacts.slice(0, 1).map((fact) => (
                <span key={fact} className="loot-preview-tag"><Swords className="size-3.5" />{fact}</span>
              ))}
            </div>
          ) : null}

          {item.description || item.notes ? (
            <p className="loot-preview-description">{item.description || item.notes}</p>
          ) : null}
        </div>
      </section>

      <section className="loot-preview-market-strip" aria-label={t('itemDetail.trade')}>
        <MarketStat
          icon={<Coins className="size-4" />}
          label={t('itemDetail.value', { defaultValue: 'Reference value' })}
          value={formatGold(item.value)}
          accent
        />
        <MarketStat
          icon={<BadgeDollarSign className="size-4" />}
          label={t('itemDetail.buyFrom', { defaultValue: 'Typical buy' })}
          value={priceRange(item.buy_from)}
        />
        <MarketStat
          icon={<ShoppingBag className="size-4" />}
          label={t('itemDetail.sellTo', { defaultValue: 'Typical sell' })}
          value={priceRange(item.sell_to)}
        />
      </section>

      <section className="loot-preview-main-grid">
        <div className="loot-preview-section loot-preview-details">
          <h3 className="loot-preview-section-title">
            <Gem className="size-4" />
            {t('itemDetail.eyebrow', { defaultValue: 'Item details' })}
          </h3>
          <div className="loot-preview-detail-list">
            <DetailRow label={t('itemDetail.slot', { defaultValue: 'Slot' })} value={primarySlot} />
            <DetailRow label={t('cyclopedia.loot.category', { defaultValue: 'Category' })} value={item.category || item.item_class || item.item_type || '—'} />
            <DetailRow label={t('itemDetail.weight')} value={displayNumber(item.weight, ' oz')} />
            <DetailRow label={t('itemDetail.level')} value={displayNumber(item.level_requirement)} />
            <DetailRow label={t('itemDetail.imbuements')} value={displayNumber(item.imbuement_slots)} />
            <DetailRow
              label={t('cyclopedia.loot.tradeable', { defaultValue: 'Tradeable' })}
              value={item.tradeable == null ? '—' : item.tradeable ? t('common.yes') : t('common.no', { defaultValue: 'No' })}
            />
          </div>
        </div>

        <div className="loot-preview-section loot-preview-drops">
          <div className="loot-preview-section-heading">
            <h3 className="loot-preview-section-title">
              <PackageOpen className="size-4" />
              {t('cyclopedia.loot.droppedBy', { defaultValue: 'Dropped by' })}
            </h3>
            {drops.length ? <span>{drops.length}</span> : null}
          </div>

          {drops.length ? (
            <div className="loot-preview-drop-list">
              {drops.slice(0, 4).map((drop) => {
                const path = dropPath(drop);
                const content = (
                  <>
                    <ImageWithFallback
                      src={drop.creature_id ? `/api/v1/creatures/${drop.creature_id}/image?placeholder=false` : null}
                      alt=""
                      className="size-9 object-contain [image-rendering:pixelated]"
                      containerClassName="loot-preview-drop-image"
                      fallbackKind={drop.is_boss ? 'boss' : 'creature'}
                      fallbackLabel={drop.creature_name}
                    />
                    <span className="loot-preview-drop-copy">
                      <strong>{drop.creature_name}</strong>
                      <small>
                        {drop.chance != null ? `${drop.chance}%` : drop.rarity || t('common.unknown', { defaultValue: 'Unknown chance' })}
                      </small>
                    </span>
                    {drop.is_boss ? <span className="loot-preview-boss-chip">{t('itemDetail.boss')}</span> : null}
                  </>
                );

                return path ? (
                  <Link key={`${drop.creature_id || drop.creature_name}-${drop.relationship_id || ''}`} to={path} className="loot-preview-drop-row">
                    {content}
                  </Link>
                ) : (
                  <div key={`${drop.creature_id || drop.creature_name}-${drop.relationship_id || ''}`} className="loot-preview-drop-row">
                    {content}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="loot-preview-empty">{t('itemDetail.noDrops')}</p>
          )}
        </div>
      </section>

      {(item.vocation_requirements.length > 0 || combatFacts.length > 1) ? (
        <section className="loot-preview-section loot-preview-vocations">
          <h3 className="loot-preview-section-title">
            <Shield className="size-4" />
            {t('itemDetail.vocations')}
          </h3>
          <div className="loot-preview-vocation-grid">
            {item.vocation_requirements.map((vocation) => (
              <span key={vocation} className="loot-preview-vocation-row">
                <Shield className="size-3.5" />
                <strong>{vocation}</strong>
                <span>{t('itemDetail.required', { defaultValue: 'Required' })}</span>
              </span>
            ))}
            {combatFacts.slice(1).map((fact) => (
              <span key={fact} className="loot-preview-vocation-row loot-preview-vocation-row--neutral">
                <Swords className="size-3.5" />
                <strong>{fact}</strong>
              </span>
            ))}
          </div>
        </section>
      ) : null}

      {drops.length > 0 ? (
        <section className="loot-preview-section loot-preview-related">
          <h3 className="loot-preview-section-title">
            <Sparkles className="size-4" />
            {t('itemDetail.relatedCreatures', { defaultValue: 'Related creatures' })}
          </h3>
          <div className="loot-preview-related-grid">
            {drops.slice(0, 3).map((drop) => {
              const path = dropPath(drop);
              const tile = (
                <>
                  <ImageWithFallback
                    src={drop.creature_id ? `/api/v1/creatures/${drop.creature_id}/image?placeholder=false` : null}
                    alt=""
                    className="size-12 object-contain [image-rendering:pixelated]"
                    containerClassName="loot-preview-related-image"
                    fallbackKind={drop.is_boss ? 'boss' : 'creature'}
                    fallbackLabel={drop.creature_name}
                  />
                  <span>{drop.creature_name}</span>
                </>
              );
              return path ? (
                <Link key={`related-${drop.creature_id || drop.creature_name}`} to={path} className="loot-preview-related-card">{tile}</Link>
              ) : (
                <div key={`related-${drop.creature_id || drop.creature_name}`} className="loot-preview-related-card">{tile}</div>
              );
            })}
          </div>
        </section>
      ) : null}

      {(tradeRows.length > 0 || relatedUsage.length > 0) ? (
        <section className="loot-preview-main-grid loot-preview-secondary-grid">
          <div className="loot-preview-section">
            <h3 className="loot-preview-section-title"><ShoppingBag className="size-4" />{t('itemDetail.trade')}</h3>
            {tradeRows.length ? (
              <div className="loot-preview-detail-list">
                {tradeRows.map((row, index) => (
                  <DetailRow key={`${row.label}-${row.value}-${index}`} label={row.label} value={row.value} />
                ))}
              </div>
            ) : <p className="loot-preview-empty">—</p>}
          </div>
          <div className="loot-preview-section">
            <h3 className="loot-preview-section-title"><PackageOpen className="size-4" />{t('itemDetail.usedFor')}</h3>
            {relatedUsage.length ? (
              <div className="loot-preview-use-list">
                {relatedUsage.map((value) => <span key={value}>{value}</span>)}
              </div>
            ) : <p className="loot-preview-empty">—</p>}
          </div>
        </section>
      ) : null}

      {bestDrop ? (
        <section className="loot-preview-tip">
          <Info className="size-5" />
          <div>
            <strong>{t('itemDetail.bestKnownSource', { defaultValue: 'Best known source' })}</strong>
            <p>
              {bestDrop.creature_name}
              {bestDrop.chance != null ? ` · ${bestDrop.chance}%` : ''}
              {bestDropZone ? ` · ${bestDropZone}` : ''}
            </p>
          </div>
        </section>
      ) : null}

      <Link
        to={itemPath}
        state={{ from: `${location.pathname}${location.search}` }}
        className="creature-preview-full-link loot-preview-full-link"
      >
        {t('cyclopedia.loot.openDetails', { defaultValue: 'Open item details' })}
        <ArrowRight className="size-4" />
      </Link>
    </article>
  );
}

function MarketStat({
  icon,
  label,
  value,
  accent = false,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="loot-preview-market-stat" data-accent={accent ? 'true' : 'false'}>
      <span>{icon}{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="loot-preview-detail-row">
      <span>{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}
