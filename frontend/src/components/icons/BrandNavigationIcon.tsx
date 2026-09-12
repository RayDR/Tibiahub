import { TIBIAHUB_BRAND } from '../../assets/brand';
import { cn } from '../ui/cn';

export type BrandNavigationIconKey =
  | 'home'
  | 'cyclopedia'
  | 'planner'
  | 'map'
  | 'guild'
  | 'search'
  | 'character'
  | 'loot'
  | 'quest'
  | 'huntZone'
  | 'npc'
  | 'admin';

interface Props {
  icon: BrandNavigationIconKey;
  className?: string;
}

const assets: Partial<Record<BrandNavigationIconKey, string>> = {
  home: TIBIAHUB_BRAND.navigation.home,
  cyclopedia: TIBIAHUB_BRAND.navigation.cyclopedia,
  planner: TIBIAHUB_BRAND.navigation.huntPlanner,
  map: TIBIAHUB_BRAND.navigation.maps,
  guild: TIBIAHUB_BRAND.navigation.guild,
  search: TIBIAHUB_BRAND.navigation.search,
  character: TIBIAHUB_BRAND.navigation.character,
  loot: TIBIAHUB_BRAND.navigation.loot,
  quest: TIBIAHUB_BRAND.navigation.quests,
  huntZone: TIBIAHUB_BRAND.navigation.huntZones,
  npc: TIBIAHUB_BRAND.navigation.npcs,
};

export default function BrandNavigationIcon({ icon, className }: Props) {
  const asset = assets[icon];
  const classes = cn('size-5 shrink-0 object-contain', className);

  if (asset) {
    return <img src={asset} alt="" aria-hidden="true" draggable={false} className={classes} />;
  }

  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={classes}
    >
      <circle cx="24" cy="24" r="7" />
      <path d="M24 5v6M24 37v6M5 24h6M37 24h6M10.6 10.6l4.2 4.2M33.2 33.2l4.2 4.2M37.4 10.6l-4.2 4.2M14.8 33.2l-4.2 4.2" />
      <circle cx="24" cy="24" r="15" strokeDasharray="2 5" />
    </svg>
  );
}
