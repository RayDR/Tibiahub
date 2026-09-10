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

export default function BrandCategoryFallbackIcon({ category, className }: BrandCategoryFallbackIconProps) {
  const classes = cn('size-6', className);

  if (category === 'creatures') {
    return <svg {...common} className={classes}><circle cx="16" cy="15" r="4" /><circle cx="32" cy="15" r="4" /><circle cx="11" cy="26" r="3.5" /><circle cx="37" cy="26" r="3.5" /><path d="M24 22c-7 0-12 6-12 12 0 3 2 5 5 5 2 0 4-2 7-2s5 2 7 2c3 0 5-2 5-5 0-6-5-12-12-12Z" /></svg>;
  }

  if (category === 'bosses') {
    return <svg {...common} className={classes}><path d="M12 19c0-8 5-13 12-13s12 5 12 13c0 5-2 8-6 11v8l-4-3-2 5-2-5-4 3v-8c-4-3-6-6-6-11Z" /><circle cx="19" cy="20" r="2.5" /><circle cx="29" cy="20" r="2.5" /><path d="m21 28 3-3 3 3M17 31h14" /></svg>;
  }

  if (category === 'items') {
    return <svg {...common} className={classes}><path d="M18 9c2 3 4 4 6 4s4-1 6-4l4 5-4 5H18l-4-5 4-5Z" /><path d="M18 19c-6 6-9 12-9 17 0 5 5 7 15 7s15-2 15-7c0-5-3-11-9-17" /><path d="M19 31c3 2 7 2 10 0M24 26v10" /></svg>;
  }

  if (category === 'quests') {
    return <svg {...common} className={classes}><path d="M14 8h22v31H14c-3 0-5-2-5-5V13c0-3 2-5 5-5Z" /><path d="M14 8v31M19 16h11M19 22h9M19 28h7" /><path d="m29 34 3 2 3-2v7l-3-2-3 2v-7Z" /></svg>;
  }

  if (category === 'zones') {
    return <svg {...common} className={classes}><circle cx="24" cy="24" r="16" /><path d="m29 15-4 10-10 4 4-10 10-4Z" /><path d="M24 4v5M24 39v5M4 24h5M39 24h5" /></svg>;
  }

  return <svg {...common} className={classes}><circle cx="18" cy="17" r="6" /><circle cx="32" cy="18" r="5" /><path d="M7 39c1-8 5-12 11-12s10 4 11 12M27 29c2-2 4-3 7-3 5 0 8 4 9 11" /></svg>;
}
