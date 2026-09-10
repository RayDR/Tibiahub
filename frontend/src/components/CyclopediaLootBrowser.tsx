import React, { useEffect, useMemo, useState } from 'react';
import { ExternalLink, PackageOpen, Skull, Tag } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from './ImageWithFallback';
import AppCard from './ui/AppCard';
import { KnowledgeBadge } from './knowledge/KnowledgeDetail';
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

const itemIdentifier = (item: ItemSearchResult) =>
  item.image_item_id ?? item.external_id ?? item.id ?? null;

const CyclopediaLootBrowser: React.FC<CyclopediaLootBrowserProps> = ({
  items,
  linkState,
  onNavigate,
}) => {
  const { t } = useTranslation();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  useEffect(() => {
    if (items.length === 0) {
      setSelectedKey(null);
      return;
    }

    setSelectedKey((current) =>
      current && items.some((item) => item.normalized_name === current)
        ? current
        : items[0].normalized_name,
    );
  }, [items]);

  const selectedItem = useMemo(
    () => items.find((item) => item.normalized_name === selectedKey) || items[0] || null,
    [items, selectedKey],
  );

  const selectedDrops = useMemo(
    () => (selectedItem ? uniqueDrops(selectedItem.drops) : []),
    [selectedItem],
  );

  return (
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_22rem] 2xl:grid-cols-[minmax(0,1fr)_26rem]">
      <div className="grid min-w-0 content-start gap-3 [grid-template-columns:repeat(auto-fill,minmax(11rem,1fr))]">
        {items.map((item) => {
          const drops = uniqueDrops(item.drops);
          const primaryDrop = drops[0];
          const labels = uniqueLabels([item.item_type, item.category]);
          const selected = selectedItem?.normalized_name === item.normalized_name;

          return (
            <button
              key={item.canonical_id || item.normalized_name}
              type="button"
              data-cyclopedia-result
              aria-pressed={selected}
              onClick={() => setSelectedKey(item.normalized_name)}
              className={`ds-enter group relative min-h-[13rem] overflow-hidden rounded-xl border bg-surface-raised/80 p-4 text-left shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-primary/45 hover:bg-surface-raised hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 ${selected ? 'border-primary/70 ring-1 ring-primary/35 shadow-lg' : 'border-line'}`}
            >
              <div className="flex min-w-0 items-start gap-3">
                <ImageWithFallback
                  src={availableItemMediaUrl(item.media)}
                  alt={item.item_name}
                  className="size-12 object-contain [image-rendering:pixelated]"
                  containerClassName="grid size-14 shrink-0 place-items-center rounded-lg border border-line/80 bg-surface-base/70"
                  fallbackLabel={item.item_name}
                />
                <div className="min-w-0 flex-1">
                  <h3 className="line-clamp-2 min-h-10 font-serif text-[1.02rem] font-semibold leading-5 text-content-primary group-hover:text-primary">
                    {item.item_name}
                  </h3>
                  {labels.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {labels.slice(0, 2).map((label) => (
                        <KnowledgeBadge key={normalizeDisplayKey(label)}>{label}</KnowledgeBadge>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 space-y-2 border-t border-line/70 pt-3 text-xs text-content-secondary">
                {primaryDrop ? (
                  <div className="flex min-w-0 items-center gap-2">
                    <Skull className="size-3.5 shrink-0 text-primary" aria-hidden="true" />
                    <span className="truncate font-medium text-content-primary">{primaryDrop.creature_name}</span>
                    {primaryDrop.is_boss ? <KnowledgeBadge tone="danger">{t('itemDetail.boss')}</KnowledgeBadge> : null}
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-content-muted">
                    <PackageOpen className="size-3.5 shrink-0" aria-hidden="true" />
                    <span>{t('cyclopedia.loot.noDropSources', { defaultValue: 'No drop source recorded' })}</span>
                  </div>
                )}

                <div className="flex min-w-0 items-center gap-2">
                  <Tag className="size-3.5 shrink-0 text-content-muted" aria-hidden="true" />
                  <span className="truncate">{labels[0] || t('common.unknown', { defaultValue: 'Unknown' })}</span>
                  {primaryDrop?.rarity ? <span className="ml-auto truncate text-primary">{primaryDrop.rarity}</span> : null}
                </div>

                {primaryDrop?.chance != null ? (
                  <div className="text-content-muted">Chance: {primaryDrop.chance}%</div>
                ) : drops.length > 1 ? (
                  <div className="text-content-muted">
                    {t('cyclopedia.items.creaturesMatched', { count: drops.length })}
                  </div>
                ) : null}
              </div>
            </button>
          );
        })}
      </div>

      {selectedItem ? (
        <aside className="min-w-0 xl:self-start">
          <AppCard className="overflow-hidden border-primary/20 bg-surface-raised/95 p-0 shadow-2xl xl:sticky xl:top-[calc(var(--app-sticky-offset)+0.75rem)]">
            <div className="border-b border-line bg-surface-base/35 p-5">
              <div className="flex items-start gap-4">
                <ImageWithFallback
                  src={availableItemMediaUrl(selectedItem.media)}
                  alt={selectedItem.item_name}
                  className="size-20 object-contain [image-rendering:pixelated]"
                  containerClassName="grid size-24 shrink-0 place-items-center rounded-xl border border-primary/25 bg-surface-base/80"
                  fallbackLabel={selectedItem.item_name}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="font-serif text-2xl font-semibold leading-tight text-content-primary">
                      {selectedItem.item_name}
                    </h2>
                    {itemIdentifier(selectedItem) != null ? (
                      <span className="shrink-0 text-xs text-content-muted">#{itemIdentifier(selectedItem)}</span>
                    ) : null}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {uniqueLabels([selectedItem.item_type, selectedItem.category]).map((label) => (
                      <KnowledgeBadge key={normalizeDisplayKey(label)}>{label}</KnowledgeBadge>
                    ))}
                    {selectedDrops[0]?.rarity ? <KnowledgeBadge tone="primary">{selectedDrops[0].rarity}</KnowledgeBadge> : null}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 divide-x divide-line border-b border-line bg-surface-base/20">
              <div className="p-4">
                <p className="text-[10px] uppercase tracking-[0.14em] text-content-muted">
                  {t('cyclopedia.loot.dropSources', { defaultValue: 'Drop sources' })}
                </p>
                <p className="mt-1 text-lg font-semibold text-content-primary">{selectedDrops.length}</p>
              </div>
              <div className="p-4">
                <p className="text-[10px] uppercase tracking-[0.14em] text-content-muted">
                  {t('cyclopedia.loot.tradeable', { defaultValue: 'Tradeable' })}
                </p>
                <p className="mt-1 text-sm font-semibold text-content-primary">
                  {selectedItem.tradeable == null
                    ? t('common.unknown', { defaultValue: 'Unknown' })
                    : selectedItem.tradeable
                      ? t('common.yes', { defaultValue: 'Yes' })
                      : t('common.no', { defaultValue: 'No' })}
                </p>
              </div>
            </div>

            <div className="p-5">
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-4 border-b border-line/70 pb-2 text-sm">
                  <span className="text-content-muted">{t('cyclopedia.loot.category', { defaultValue: 'Category' })}</span>
                  <span className="max-w-[60%] truncate text-right font-medium text-content-primary">
                    {selectedItem.category || selectedItem.item_type || t('common.unknown', { defaultValue: 'Unknown' })}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4 border-b border-line/70 pb-2 text-sm">
                  <span className="text-content-muted">{t('cyclopedia.loot.stackable', { defaultValue: 'Stackable' })}</span>
                  <span className="font-medium text-content-primary">
                    {selectedItem.stackable == null
                      ? t('common.unknown', { defaultValue: 'Unknown' })
                      : selectedItem.stackable
                        ? t('common.yes', { defaultValue: 'Yes' })
                        : t('common.no', { defaultValue: 'No' })}
                  </span>
                </div>
              </div>

              <div className="mt-5">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h3 className="font-serif text-lg font-semibold text-content-primary">
                    {t('cyclopedia.loot.droppedBy', { defaultValue: 'Dropped by' })}
                  </h3>
                  {selectedDrops.length > 0 ? <span className="text-xs text-content-muted">{selectedDrops.length}</span> : null}
                </div>

                {selectedDrops.length > 0 ? (
                  <div className="space-y-2">
                    {selectedDrops.slice(0, 6).map((drop) => (
                      <div key={`${selectedItem.normalized_name}-${normalizeDisplayKey(drop.creature_name)}`} className="flex min-w-0 items-center gap-2 rounded-lg border border-line/70 bg-surface-base/35 px-3 py-2.5">
                        <Skull className="size-4 shrink-0 text-primary" aria-hidden="true" />
                        <div className="min-w-0 flex-1">
                          {drop.creature_slug || drop.creature_id ? (
                            <Link
                              to={`/creatures/${drop.creature_slug || drop.creature_id}`}
                              state={linkState}
                              onClick={onNavigate}
                              className="block truncate text-sm font-medium text-content-primary hover:text-primary hover:underline"
                            >
                              {drop.creature_name}
                            </Link>
                          ) : (
                            <span className="block truncate text-sm font-medium text-content-primary">{drop.creature_name}</span>
                          )}
                          <div className="mt-0.5 flex gap-2 text-[11px] text-content-muted">
                            {drop.rarity ? <span>{drop.rarity}</span> : null}
                            {drop.chance != null ? <span>{drop.chance}%</span> : null}
                          </div>
                        </div>
                        {drop.is_boss ? <KnowledgeBadge tone="danger">{t('itemDetail.boss')}</KnowledgeBadge> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="rounded-lg border border-dashed border-line p-4 text-sm text-content-muted">
                    {t('cyclopedia.loot.noDropSources', { defaultValue: 'No drop source recorded for this item yet.' })}
                  </p>
                )}
              </div>

              <Link
                to={itemPath(selectedItem)}
                state={linkState}
                onClick={onNavigate}
                className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/35 bg-primary/10 px-4 py-2.5 text-sm font-semibold text-primary transition hover:bg-primary/15"
              >
                {t('cyclopedia.loot.openDetails', { defaultValue: 'Open item details' })}
                <ExternalLink className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </AppCard>
        </aside>
      ) : null}
    </div>
  );
};

export default CyclopediaLootBrowser;
