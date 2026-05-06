import { IconDefinition } from '@fortawesome/fontawesome-svg-core';
import { faCrown, faDragon, faGem, faMapLocationDot, faScroll } from '@fortawesome/free-solid-svg-icons';

export type CyclopediaTabKey = 'creatures' | 'bosses' | 'loot' | 'quests' | 'zones';
export type CyclopediaMode = 'creatures' | 'bosses' | 'items' | 'quests' | 'zones';

export interface CyclopediaSection {
  key: CyclopediaTabKey;
  i18nLabel: string;
  icon: IconDefinition;
  mode: CyclopediaMode;
}

export const cyclopediaSections: CyclopediaSection[] = [
  { key: 'creatures', i18nLabel: 'nav.creatures', icon: faDragon, mode: 'creatures' },
  { key: 'bosses', i18nLabel: 'nav.bosses', icon: faCrown, mode: 'bosses' },
  { key: 'loot', i18nLabel: 'nav.loot', icon: faGem, mode: 'items' },
  { key: 'quests', i18nLabel: 'nav.quests', icon: faScroll, mode: 'quests' },
  { key: 'zones', i18nLabel: 'nav.zones', icon: faMapLocationDot, mode: 'zones' },
];

export const tabToMode = (tab: string): CyclopediaMode | null => {
  const found = cyclopediaSections.find((section) => section.key === tab);
  return found ? found.mode : null;
};

export const modeToTab = (mode: CyclopediaMode): CyclopediaTabKey => {
  const found = cyclopediaSections.find((section) => section.mode === mode);
  return (found?.key || 'creatures') as CyclopediaTabKey;
};
