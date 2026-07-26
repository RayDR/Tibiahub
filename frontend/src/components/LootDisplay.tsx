import React, { useMemo, useState } from 'react';

import type { Loot } from '../types';
import ImageWithFallback from './ImageWithFallback';

interface LootDisplayProps {
  items: Loot[];
}

const RARITY_RANK: Record<string, number> = {
  'Very Rare': 0,
  Rare: 1,
  'Semi-rare': 2,
  Uncommon: 3,
  Common: 4,
  Always: 5,
};

const rarityRank = (rarity?: string): number => {
  if (!rarity) return 99;
  return RARITY_RANK[rarity] ?? 98;
};

const LootDisplay: React.FC<LootDisplayProps> = ({ items }) => {
  const [showAll, setShowAll] = useState(false);

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const rarityDiff = rarityRank(a.rarity) - rarityRank(b.rarity);
      if (rarityDiff !== 0) return rarityDiff;
      return (b.percentage ?? -1) - (a.percentage ?? -1);
    });
  }, [items]);

  const visibleItems = showAll ? sortedItems : sortedItems.slice(0, 20);

  if (sortedItems.length === 0) {
    return <div className="text-sm text-content-muted">No drop data available.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visibleItems.map((loot) => (
          <div key={loot.id} className="rounded-xl border border-line bg-surface-base/50 p-4">
            <div className="mb-3 flex items-center gap-3">
              <ImageWithFallback
                src={loot.item_image_url ? `/api/v1/items/${loot.id}/image` : null}
                alt={loot.item_name}
                className="h-12 w-12 rounded-lg object-contain bg-surface"
                containerClassName="h-12 w-12"
                fallbackLabel="Item"
              />
              <div className="min-w-0">
                <div className="truncate font-semibold text-content-primary">{loot.item_name}</div>
                <div className="text-xs text-content-muted">
                  Rarity: {loot.rarity || 'Unknown'}
                </div>
              </div>
            </div>

            <div className="space-y-1 text-xs text-content-secondary">
              <div>Chance: {loot.percentage !== null && loot.percentage !== undefined ? `${loot.percentage}%` : 'Not available'}</div>
              <div>Amount: {loot.min_amount} - {loot.max_amount}</div>
            </div>

            {loot.source_url && (
              <a href={loot.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-primary hover:text-primary">
                Source page
              </a>
            )}
          </div>
        ))}
      </div>

      {!showAll && sortedItems.length > 20 && (
        <button
          onClick={() => setShowAll(true)}
          className="w-full rounded-lg border border-primary/30 px-4 py-2 text-sm text-primary transition hover:bg-primary/10"
        >
          Show more ({sortedItems.length - 20} remaining)
        </button>
      )}
    </div>
  );
};

export default LootDisplay;
