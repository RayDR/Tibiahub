import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Coins,
  Gem,
  Loader2,
  PackageOpen,
  Shield,
  ShoppingBag,
  Swords,
  Weight,
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from '../ImageWithFallback';
import { itemsApi } from '../../services/api';
import type { ItemDetail } from '../../types';
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

  const acquisition = useMemo(() => item?.drops.slice(0, 5) || [], [item]);
  const combatFacts = useMemo(() => {
    if (!item) return [];
    return [
      item.attack != null ? { label: t('itemDetail.attack'), value: item.attack } : null,
      item.defense != null ? { label: t('itemDetail.defense'), value: item.defense } : null,
      item.armor != null ? { label: t('itemDetail.armor'), value: item.armor } : null,
      item.range != null ? { label: t('itemDetail.range'), value: item.range } : null,
    ].filter((fact): fact is { label: string; value: number } => Boolean(fact));
  }, [item, t]);

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
  const badges = [item.category, item.item_type, item.item_class, item.rarity].filter(
    (value): value is string => Boolean(value),
  );
  const tradeRows = [
    ...item.buy_from.slice(0, 2).map((row) => ({ label: t('itemDetail.buyFrom'), value: displayRecord(row) })),
    ...item.sell_to.slice(0, 2).map((row) => ({ label: t('itemDetail.sellTo'), value: displayRecord(row) })),
  ];
  const hasUsage = item.required_for.length > 0 || item.rewards_from.length > 0;

  return (
    <article className="creature-preview-panel loot-preview-panel" data-item-preview-panel>
      <section className="creature-preview-identity loot-preview-identity">
        <div className="creature-preview-sprite loot-preview-sprite">
          <ImageWithFallback
            src={itemMediaUrl}
            alt={item.item_name}
            className="size-full object-contain [image-rendering:pixelated]"
            containerClassName="size-full"
            fallbackKind="item"
            fallbackLabel={item.item_name}
          />
        </div>
        <div className="min-w-0">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary">
                {t('nav.loot')}
              </p>
              <h2 className="creature-preview-name break-words">{item.item_name}</h2>
            </div>
            {item.game_item_id != null ? (
              <span className="shrink-0 text-[10px] font-semibold text-content-muted">#{item.game_item_id}</span>
            ) : null}
          </div>
          {badges.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {badges.map((badge) => (
                <span key={badge} className="creature-preview-chip">{badge}</span>
              ))}
            </div>
          ) : null}
          {item.description || item.notes ? (
            <p className="mt-3 line-clamp-4 text-sm leading-6 text-content-secondary">
              {item.description || item.notes}
            </p>
          ) : null}
        </div>
      </section>

      <section className="creature-preview-stats" aria-label={t('itemDetail.eyebrow')}>
        <PreviewStat icon={<Coins className="size-3.5" />} label={t('itemDetail.value')} value={displayNumber(item.value, ' gp')} />
        <PreviewStat icon={<Weight className="size-3.5" />} label={t('itemDetail.weight')} value={displayNumber(item.weight, ' oz')} />
        <PreviewStat icon={<Gem className="size-3.5" />} label={t('itemDetail.level')} value={displayNumber(item.level_requirement)} />
      </section>

      <section className="creature-preview-columns loot-preview-columns">
        <div className="min-w-0">
          <h3 className="creature-preview-section-title"><Swords className="size-4 text-primary" />{t('itemDetail.combat')}</h3>
          {combatFacts.length ? (
            <div className="creature-preview-list">
              {combatFacts.map((fact) => (
                <div key={fact.label} className="creature-preview-row">
                  <span>{fact.label}</span><strong className="text-content-primary">{fact.value.toLocaleString()}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xs text-content-muted">{t('itemDetail.noDrops', { defaultValue: 'No combat properties documented.' })}</p>
          )}
          {(item.slots.length > 0 || item.imbuement_slots != null) ? (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {item.slots.slice(0, 4).map((slot) => <span key={slot} className="creature-preview-chip">{slot}</span>)}
              {item.imbuement_slots != null ? <span className="creature-preview-chip">{t('itemDetail.imbuements')}: {item.imbuement_slots}</span> : null}
            </div>
          ) : null}
        </div>

        <div className="min-w-0">
          <h3 className="creature-preview-section-title"><Shield className="size-4 text-primary" />{t('itemDetail.attributes')}</h3>
          <div className="creature-preview-list">
            <div className="creature-preview-row"><span>{t('itemDetail.trade', { defaultValue: 'Tradeable' })}</span><strong className="text-content-primary">{item.tradeable == null ? '—' : item.tradeable ? t('common.yes') : t('common.no', { defaultValue: 'No' })}</strong></div>
            <div className="creature-preview-row"><span>Stackable</span><strong className="text-content-primary">{item.stackable == null ? '—' : item.stackable ? t('common.yes') : t('common.no', { defaultValue: 'No' })}</strong></div>
            <div className="creature-preview-row"><span>{t('itemDetail.vocations')}</span><strong className="max-w-[10rem] truncate text-content-primary">{item.vocation_requirements.length ? item.vocation_requirements.join(', ') : '—'}</strong></div>
          </div>
        </div>
      </section>

      <section className="loot-preview-acquisition">
        <div className="flex items-center justify-between gap-3">
          <h3 className="creature-preview-section-title"><PackageOpen className="size-4 text-primary" />{t('itemDetail.acquisition')}</h3>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-content-muted">{item.drops.length} drops</span>
        </div>
        {acquisition.length ? (
          <div className="mt-3 grid gap-2">
            {acquisition.map((drop) => (
              <div key={`${drop.creature_id || drop.creature_name}-${drop.relationship_id || ''}`} className="loot-preview-drop-row">
                <ImageWithFallback
                  src={drop.creature_id ? `/api/v1/creatures/${drop.creature_id}/image?placeholder=false` : null}
                  alt=""
                  className="size-10 object-contain [image-rendering:pixelated]"
                  containerClassName="grid size-10 shrink-0 place-items-center"
                  fallbackKind={drop.is_boss ? 'boss' : 'creature'}
                  fallbackLabel={drop.creature_name}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate text-sm font-semibold text-content-primary">{drop.creature_name}</span>
                    {drop.is_boss ? <span className="creature-preview-chip">Boss</span> : null}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-content-muted">
                    {drop.chance != null ? <span>{t('itemDetail.chance', { value: drop.chance })}</span> : null}
                    {drop.rarity ? <span>{drop.rarity}</span> : null}
                    {drop.hunt_zones[0]?.name ? <span className="truncate">{drop.hunt_zones[0].name}</span> : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-content-muted">{t('itemDetail.noDrops')}</p>
        )}
      </section>

      {(tradeRows.length > 0 || hasUsage) ? (
        <section className="creature-preview-columns loot-preview-columns">
          <div className="min-w-0">
            <h3 className="creature-preview-section-title"><ShoppingBag className="size-4 text-primary" />{t('itemDetail.trade')}</h3>
            {tradeRows.length ? (
              <div className="creature-preview-list">
                {tradeRows.map((row, index) => (
                  <div key={`${row.label}-${row.value}-${index}`} className="creature-preview-row"><span>{row.label}</span><strong className="max-w-[10rem] truncate text-content-primary">{row.value}</strong></div>
                ))}
              </div>
            ) : <p className="mt-2 text-xs text-content-muted">—</p>}
          </div>
          <div className="min-w-0">
            <h3 className="creature-preview-section-title"><PackageOpen className="size-4 text-primary" />{t('itemDetail.usedFor')}</h3>
            {hasUsage ? (
              <div className="creature-preview-list">
                {[...item.required_for.slice(0, 2), ...item.rewards_from.slice(0, 2)].map((value) => (
                  <div key={value} className="creature-preview-row"><span className="truncate">{value}</span></div>
                ))}
              </div>
            ) : <p className="mt-2 text-xs text-content-muted">—</p>}
          </div>
        </section>
      ) : null}

      <Link
        to={itemPath}
        state={{ from: `${location.pathname}${location.search}` }}
        className="creature-preview-full-link"
      >
        {t('itemDetail.eyebrow')} <ArrowRight className="size-4" />
      </Link>
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
