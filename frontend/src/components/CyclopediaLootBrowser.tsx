import React from 'react';
import {
  ArrowUpRight,
  Layers3,
  PackageOpen,
  Percent,
  ShieldCheck,
  Skull,
  Sparkles,
  Tag,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from './ImageWithFallback';
import { KnowledgeBadge } from './knowledge/KnowledgeDetail';
import { useOptionalCyclopediaPreviewSelection } from './cyclopedia/CyclopediaPreviewSelectionContext';
import type { ItemSearchResult } from '../types';
import { availableItemMediaUrl } from '../utils/entityMedia';

interface CyclopediaLootBrowserProps {
  items: ItemSearchResult[];
  linkState?: unknown;
  onNavigate?: () => void;
}

const normalizeDisplayKey = (value?: string | null) =>
  String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');

const uniqueLabels = (values: Array<string | null | undefined>) => {
  const seen = new Set<string>();
  return values.filter((value): value is string => {
    if (!value?.trim()) return false;
    const key = normalizeDisplayKey(value);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const uniqueDrops = (drops: ItemSearchResult['drops']) => {
  const seen = new Set<string>();
  return drops.filter((drop) => {
    const key = normalizeDisplayKey(drop.creature_name);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const itemPath = (item: ItemSearchResult) =>
  `/items/${item.slug || item.normalized_name.split(' ').join('-')}`;

const itemPreviewIdentifier = (item: ItemSearchResult): string =>
  item.slug
  || item.external_id
  || (item.id != null ? String(item.id) : '')
  || item.normalized_name;

const rarityKey = (value?: string | null): string =>
  normalizeDisplayKey(value).replace(/[^a-z0-9]+/g, '-');

const CyclopediaLootBrowser: React.FC<CyclopediaLootBrowserProps> = ({
  items,
  linkState,
  onNavigate,
}) => {
  const { t } = useTranslation();
  const preview = useOptionalCyclopediaPreviewSelection();

  return (
    <div className="loot-cyclopedia-grid">
      {items.map((item) => {
        const drops = uniqueDrops(item.drops);
        const primaryDrop = drops[0];
        const labels = uniqueLabels([item.item_type, item.category]);
        const identifier = itemPreviewIdentifier(item);
        const selected = preview?.selection?.kind === 'item'
          && preview.selection.identifier === identifier;
        const rarity = primaryDrop?.rarity || null;
        const bestChance = drops.reduce<number | null>((best, drop) => {
          if (drop.chance == null) return best;
          return best == null ? drop.chance : Math.max(best, drop.chance);
        }, null);

        return (
          <article
            key={item.canonical_id || item.normalized_name}
            data-cyclopedia-result
            data-cyclopedia-item-card="true"
            data-item-identifier={identifier}
            data-selected={selected ? 'true' : 'false'}
            className="loot-cyclopedia-card"
          >
            <button
              type="button"
              className="loot-cyclopedia-card__select"
              onClick={() => preview?.select({ kind: 'item', identifier })}
              aria-pressed={selected}
              aria-label={item.item_name}
            >
              <div className="loot-cyclopedia-card__media">
                <ImageWithFallback
                  src={availableItemMediaUrl(item.media)}
                  alt={item.item_name}
                  className="loot-cyclopedia-card__image [image-rendering:pixelated]"
                  containerClassName="loot-cyclopedia-card__image-shell"
                  fallbackKind="item"
                  fallbackLabel={item.item_name}
                />
                <span className="loot-cyclopedia-card__crest" aria-hidden="true">
                  <Sparkles className="size-4" />
                </span>
              </div>

              <div className="loot-cyclopedia-card__identity">
                <div className="loot-cyclopedia-card__title-row">
                  <h3>{item.item_name}</h3>
                  {rarity ? (
                    <span className="loot-rarity-chip" data-rarity={rarityKey(rarity)} title={rarity}>
                      {rarity}
                    </span>
                  ) : null}
                </div>

                <div className="loot-cyclopedia-card__facts">
                  {primaryDrop ? (
                    <div className="loot-cyclopedia-card__fact">
                      <Skull className="size-3.5 shrink-0" aria-hidden="true" />
                      <span className="truncate">{primaryDrop.creature_name}</span>
                      {primaryDrop.is_boss ? (
                        <KnowledgeBadge tone="danger">{t('itemDetail.boss')}</KnowledgeBadge>
                      ) : null}
                    </div>
                  ) : (
                    <div className="loot-cyclopedia-card__fact loot-cyclopedia-card__fact--muted">
                      <PackageOpen className="size-3.5 shrink-0" aria-hidden="true" />
                      <span>{t('cyclopedia.loot.noDropSources', { defaultValue: 'No drop source recorded' })}</span>
                    </div>
                  )}

                  <div className="loot-cyclopedia-card__fact loot-cyclopedia-card__fact--muted">
                    <Tag className="size-3.5 shrink-0" aria-hidden="true" />
                    <span className="truncate">{labels[0] || t('common.unknown', { defaultValue: 'Unknown' })}</span>
                  </div>

                  {bestChance != null ? (
                    <div className="loot-cyclopedia-card__fact loot-cyclopedia-card__fact--accent">
                      <Percent className="size-3.5 shrink-0" aria-hidden="true" />
                      <span>{t('itemDetail.chance', { value: bestChance, defaultValue: `${bestChance}% best known drop` })}</span>
                    </div>
                  ) : drops.length > 1 ? (
                    <div className="loot-cyclopedia-card__fact loot-cyclopedia-card__fact--muted">
                      <Layers3 className="size-3.5 shrink-0" aria-hidden="true" />
                      <span>{t('cyclopedia.items.creaturesMatched', { count: drops.length })}</span>
                    </div>
                  ) : (
                    <div className="loot-cyclopedia-card__fact loot-cyclopedia-card__fact--muted">
                      <ShieldCheck className="size-3.5 shrink-0" aria-hidden="true" />
                      <span>
                        {item.tradeable == null
                          ? t('common.unknown', { defaultValue: 'Unknown' })
                          : item.tradeable
                            ? t('cyclopedia.loot.tradeable', { defaultValue: 'Tradeable' })
                            : t('common.no', { defaultValue: 'No' })}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </button>

            <Link
              to={itemPath(item)}
              state={linkState}
              onClick={onNavigate}
              className="loot-cyclopedia-card__details"
              aria-label={t('cyclopedia.loot.openDetails', { defaultValue: 'Open item details' })}
              title={t('cyclopedia.loot.openDetails', { defaultValue: 'Open item details' })}
            >
              <ArrowUpRight className="size-3.5" />
            </Link>
          </article>
        );
      })}
    </div>
  );
};

export default CyclopediaLootBrowser;
