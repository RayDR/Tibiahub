import homeNav from './navigation/home.png';
import searchNav from './navigation/search.png';
import cyclopediaNav from './navigation/cyclopedia.png';
import huntPlannerNav from './navigation/hunt_planner.png';
import mapNav from './navigation/map.png';
import guildNav from './navigation/guild.png';
import characterNav from './navigation/character_selector.png';
import huntZoneNav from './navigation/hunt_zone.png';
import npcNav from './navigation/npc.png';
import lootNav from './navigation/loot.png';
import questNav from './navigation/quest.png';

import cyclopediaTitle from './page-titles/cyclopedia_title_asset.png';
import huntPlannerTitle from './page-titles/hunt_planner_title_asset.png';
import mapTitle from './page-titles/map_title_asset.png';
import guildTitle from './page-titles/guild_title_asset.png';
import questTitle from './page-titles/quest_title_asset.png';
import huntZoneTitle from './page-titles/hunt_zone_title_asset.png';
import lootTitle from './page-titles/loot_title_asset.png';
import npcTitle from './page-titles/npc_title_asset.png';

import cyclopediaModule from './modules/enchanted_golden_grimoire.png';
import huntPlannerModule from './modules/enchanted_hunt_planner_scroll.png';
import mapModule from './modules/enchanted_golden_atlas_map.png';
import questModule from './modules/ornate_compass_quest_scroll.png';
import huntZoneModule from './modules/ornate_golden_hunt_zone_compass.png';
import lootModule from './modules/ornate_blue_gold_loot_pouch.png';
import npcModule from './modules/engraved_npc_compass_medallion.png';
import worldCitadelModule from './modules/moonlit_citadel_in_the_mist.png';

import searchSection from './sections/ornate_golden_fantasy_magnifying_glass.png';
import questSection from './sections/ornate_compass_quest_scroll.png';
import huntZoneSection from './sections/ornate_golden_hunt_zone_compass.png';
import lootSection from './sections/ornate_blue_gold_loot_pouch.png';
import npcSection from './sections/engraved_npc_compass_medallion.png';
import guildSection from './sections/gilded_guild_avatar_emblem.png';
import cyclopediaSection from './sections/ornate_golden_open_book_emblem.png';

import tibiaHubHeraldicLogo from './logo/main/tibiahub_heraldic_crest_logo.png';
import tibiaHubFantasyLogo from './logo/main/tibiahub_fantasy_crest_logo.png';
import tibiaHubGoldenLogo from './logo/main/golden_tibiahub_heraldic_crest_logo.png';

export const TIBIAHUB_BRAND = {
  navigation: {
    home: homeNav,
    search: searchNav,
    cyclopedia: cyclopediaNav,
    huntPlanner: huntPlannerNav,
    maps: mapNav,
    guild: guildNav,
    character: characterNav,
    huntZones: huntZoneNav,
    npcs: npcNav,
    loot: lootNav,
    quests: questNav,
  },
  pageTitles: {
    cyclopedia: cyclopediaTitle,
    huntPlanner: huntPlannerTitle,
    maps: mapTitle,
    guild: guildTitle,
    quests: questTitle,
    huntZones: huntZoneTitle,
    loot: lootTitle,
    npcs: npcTitle,
  },
  modules: {
    cyclopedia: cyclopediaModule,
    huntPlanner: huntPlannerModule,
    maps: mapModule,
    quests: questModule,
    huntZones: huntZoneModule,
    loot: lootModule,
    npcs: npcModule,
    worldCitadel: worldCitadelModule,
  },
  sections: {
    search: searchSection,
    cyclopedia: cyclopediaSection,
    quests: questSection,
    huntZones: huntZoneSection,
    loot: lootSection,
    npcs: npcSection,
    guild: guildSection,
  },
  logoCandidates: {
    heraldic: tibiaHubHeraldicLogo,
    fantasy: tibiaHubFantasyLogo,
    golden: tibiaHubGoldenLogo,
  },
} as const;

export type TibiaHubNavigationAssetKey = keyof typeof TIBIAHUB_BRAND.navigation;
export type TibiaHubPageTitleAssetKey = keyof typeof TIBIAHUB_BRAND.pageTitles;
export type TibiaHubModuleAssetKey = keyof typeof TIBIAHUB_BRAND.modules;
