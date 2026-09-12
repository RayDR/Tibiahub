import { TIBIAHUB_BRAND } from '../../assets/brand';
import { cn } from '../ui/cn';

export type BrandCategoryKey = 'creatures' | 'bosses' | 'items' | 'quests' | 'zones' | 'npcs';

interface BrandCategoryFallbackIconProps {
  category: BrandCategoryKey;
  className?: string;
}

const common = {
  viewBox: '0 0 48 48',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.4,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
};

const brandedFallbacks: Partial<Record<BrandCategoryKey, string>> = {
  items: TIBIAHUB_BRAND.sections.loot,
  quests: TIBIAHUB_BRAND.sections.quests,
  zones: TIBIAHUB_BRAND.sections.huntZones,
  npcs: TIBIAHUB_BRAND.sections.npcs,
};

export default function BrandCategoryFallbackIcon({ category, className }: BrandCategoryFallbackIconProps) {
  const classes = cn('size-6', className);
  const branded = brandedFallbacks[category];

  if (branded) {
    return <img src={branded} alt="" aria-hidden="true" draggable={false} className={cn(classes, 'object-contain')} />;
  }

  if (category === 'creatures') {
    return <svg {...common} className={classes}><circle cx="16" cy="15" r="4" /><circle cx="32" cy="15" r="4" /><circle cx="11" cy="26" r="3.5" /><circle cx="37" cy="26" r="3.5" /><path d="M24 22c-7 0-12 6-12 12 0 3 2 5 5 5 2 0 4-2 7-2s5 2 7 2c3 0 5-2 5-5 0-6-5-12-12-12Z" /></svg>;
  }

  return <svg {...common} className={classes}><path d="M12 19c0-8 5-13 12-13s12 5 12 13c0 5-2 8-6 11v8l-4-3-2 5-2-5-4 3v-8c-4-3-6-6-6-11Z" /><circle cx="19" cy="20" r="2.5" /><circle cx="29" cy="20" r="2.5" /><path d="m21 28 3-3 3 3M17 31h14" /></svg>;
}
