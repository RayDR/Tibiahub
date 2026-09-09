import { cn } from '../ui/cn';

export type BrandNavigationIconKey = 'home' | 'cyclopedia' | 'planner' | 'map' | 'guild' | 'admin';

interface Props {
  icon: BrandNavigationIconKey;
  className?: string;
}

const common = {
  viewBox: '0 0 48 48',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
};

export default function BrandNavigationIcon({ icon, className }: Props) {
  const classes = cn('size-5', className);

  if (icon === 'home') {
    return <svg {...common} className={classes}><path d="M7 23 24 8l17 15" /><path d="M11 21v19h26V21M20 40V28h8v12" /><path d="M17 14h14" /></svg>;
  }

  if (icon === 'cyclopedia') {
    return <svg {...common} className={classes}><path d="M7 11c7-2 12 0 17 4v25c-5-4-10-6-17-4V11Z" /><path d="M41 11c-7-2-12 0-17 4v25c5-4 10-6 17-4V11Z" /><path d="M24 15v25M12 17c3 0 6 .7 9 2M36 17c-3 0-6 .7-9 2" /></svg>;
  }

  if (icon === 'planner') {
    return <svg {...common} className={classes}><circle cx="24" cy="24" r="17" /><path d="m30 15-4 11-11 4 4-11 11-4Z" /><path d="M24 5v5M24 38v5M5 24h5M38 24h5" /><path d="m31 31 7 7" /></svg>;
  }

  if (icon === 'map') {
    return <svg {...common} className={classes}><path d="m7 10 11-4 12 5 11-4v31l-11 4-12-5-11 4V10Z" /><path d="M18 6v31M30 11v31" /><path d="m11 18 4-2M34 18l4-2M21 24l6 3" /></svg>;
  }

  if (icon === 'guild') {
    return <svg {...common} className={classes}><path d="M24 5 39 11v11c0 10-6 17-15 21C15 39 9 32 9 22V11l15-6Z" /><path d="m16 25 5 5 11-12" /><path d="M18 13h12" /></svg>;
  }

  return <svg {...common} className={classes}><circle cx="24" cy="24" r="7" /><path d="M24 5v6M24 37v6M5 24h6M37 24h6M10.6 10.6l4.2 4.2M33.2 33.2l4.2 4.2M37.4 10.6l-4.2 4.2M14.8 33.2l-4.2 4.2" /><circle cx="24" cy="24" r="15" strokeDasharray="2 5" /></svg>;
}
