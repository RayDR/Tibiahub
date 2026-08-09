import React from 'react';

type IconProps = { className?: string };

const base = 'h-4 w-4';

export const CreatureCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M4 17c2-3 5-5 8-5s6 2 8 5" />
    <path d="M8 10l2-3 2 2 2-2 2 3" />
    <circle cx="10" cy="12" r="1" fill="currentColor" />
    <circle cx="14" cy="12" r="1" fill="currentColor" />
  </svg>
);

export const DemonCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M6 18c1-5 3-7 6-7s5 2 6 7" />
    <path d="M9 7l-2-3M15 7l2-3" />
    <path d="M10 14h4" />
  </svg>
);

export const DragonCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M4 15c3-4 7-6 11-6" />
    <path d="M15 9l3-3 2 2-3 3" />
    <path d="M9 12l-2 4 4-2" />
    <circle cx="13" cy="10" r="1" fill="currentColor" />
  </svg>
);

export const BeastCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 16c2-2 4-3 7-3s5 1 7 3" />
    <path d="M7 10l-2-2M17 10l2-2" />
    <path d="M10 15h4" />
  </svg>
);

export const UndeadCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M7 18c0-4 2-6 5-6s5 2 5 6" />
    <circle cx="10" cy="10" r="1" fill="currentColor" />
    <circle cx="14" cy="10" r="1" fill="currentColor" />
    <path d="M9 14h6" />
  </svg>
);

export const ConstructCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="6" y="8" width="12" height="10" rx="2" />
    <path d="M10 5h4M12 5v3" />
    <circle cx="10" cy="13" r="1" fill="currentColor" />
    <circle cx="14" cy="13" r="1" fill="currentColor" />
  </svg>
);

export const ElementalCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 4c3 3 5 6 5 9a5 5 0 11-10 0c0-3 2-6 5-9z" />
    <path d="M12 10v6" />
  </svg>
);

export const HumanoidCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="7" r="3" />
    <path d="M6 20c0-5 2-8 6-8s6 3 6 8" />
  </svg>
);

export const MagicalCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" />
    <path d="M18 15l.8 2.2L21 18l-2.2.8L18 21l-.8-2.2L15 18l2.2-.8L18 15z" />
  </svg>
);

export const PlantCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 21V9" />
    <path d="M12 12C7 12 5 9 5 5c4 0 7 2 7 7z" />
    <path d="M12 15c5 0 7-3 7-7-4 0-7 2-7 7z" />
  </svg>
);

export const SlimeCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 17c0-5 2-10 7-13 5 3 7 8 7 13 0 2-2 3-4 3H9c-2 0-4-1-4-3z" />
    <circle cx="10" cy="14" r="1" fill="currentColor" />
    <circle cx="15" cy="14" r="1" fill="currentColor" />
  </svg>
);

export const DimensionalCategoryIcon: React.FC<IconProps> = ({ className = '' }) => (
  <svg viewBox="0 0 24 24" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="7" />
    <path d="M12 5c3 2 4 4 4 7s-1 5-4 7c-3-2-4-4-4-7s1-5 4-7z" />
    <path d="M5 12h14" />
  </svg>
);

export const iconByCategory = (category: string) => {
  switch ((category || '').toLowerCase()) {
    case 'demon':
      return DemonCategoryIcon;
    case 'dragon':
    case 'reptile':
      return DragonCategoryIcon;
    case 'mammal':
    case 'bird':
    case 'amphibic':
    case 'aquatic':
    case 'vermin':
      return BeastCategoryIcon;
    case 'undead':
      return UndeadCategoryIcon;
    case 'construct':
      return ConstructCategoryIcon;
    case 'elemental':
      return ElementalCategoryIcon;
    case 'human':
    case 'humanoid':
    case 'giant':
    case 'lycanthrope':
      return HumanoidCategoryIcon;
    case 'magical':
    case 'fey':
    case 'inkborn':
      return MagicalCategoryIcon;
    case 'plant':
      return PlantCategoryIcon;
    case 'slime':
      return SlimeCategoryIcon;
    case 'extra dimensional':
      return DimensionalCategoryIcon;
    default:
      return CreatureCategoryIcon;
  }
};
