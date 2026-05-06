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

export const iconByCategory = (category: string) => {
  switch ((category || '').toLowerCase()) {
    case 'demon':
      return DemonCategoryIcon;
    case 'dragon':
      return DragonCategoryIcon;
    case 'beast':
    case 'mammal':
    case 'bird':
    case 'amphibic':
    case 'aquatic':
      return BeastCategoryIcon;
    case 'undead':
      return UndeadCategoryIcon;
    case 'construct':
      return ConstructCategoryIcon;
    case 'elemental':
      return ElementalCategoryIcon;
    default:
      return CreatureCategoryIcon;
  }
};
