export type CyclopediaTabKey = 'creatures' | 'bosses' | 'loot' | 'quests' | 'zones' | 'npcs';
export type CyclopediaMode = 'creatures' | 'bosses' | 'items' | 'quests' | 'zones' | 'npcs';

export interface CyclopediaSection {
  key: CyclopediaTabKey;
  i18nLabel: string;
  mode: CyclopediaMode;
}

export const cyclopediaSections: CyclopediaSection[] = [
  { key: 'creatures', i18nLabel: 'nav.creatures', mode: 'creatures' },
  { key: 'bosses', i18nLabel: 'nav.bosses', mode: 'bosses' },
  { key: 'loot', i18nLabel: 'nav.loot', mode: 'items' },
  { key: 'quests', i18nLabel: 'nav.quests', mode: 'quests' },
  { key: 'zones', i18nLabel: 'nav.zones', mode: 'zones' },
  { key: 'npcs', i18nLabel: 'nav.npcs', mode: 'npcs' },
];

export const tabToMode = (tab: string): CyclopediaMode | null => {
  const found = cyclopediaSections.find((section) => section.key === tab);
  return found ? found.mode : null;
};

export const modeToTab = (mode: CyclopediaMode): CyclopediaTabKey => {
  const found = cyclopediaSections.find((section) => section.mode === mode);
  return (found?.key || 'creatures') as CyclopediaTabKey;
};
