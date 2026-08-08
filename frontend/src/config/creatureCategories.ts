export const CREATURE_CATEGORIES = [
  '',
  'Amphibic',
  'Aquatic',
  'Bird',
  'Construct',
  'Demon',
  'Dragon',
  'Elemental',
  'Extra Dimensional',
  'Fey',
  'Giant',
  'Human',
  'Humanoid',
  'Inkborn',
  'Lycanthrope',
  'Magical',
  'Mammal',
  'Plant',
  'Reptile',
  'Slime',
  'Undead',
  'Vermin',
] as const;

export type CreatureCategory =
  (typeof CREATURE_CATEGORIES)[number];

export const normalizeCreatureCategory = (
  value: string | null,
): CreatureCategory => {
  const normalized = (value || '').trim().toLowerCase();

  if (!normalized) return '';

  return (
    CREATURE_CATEGORIES.find(
      (category) =>
        category.toLowerCase() === normalized,
    ) ?? ''
  );
};

export const normalizeCategoryKey = (
  value: string,
): string =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
