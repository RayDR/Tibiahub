import fs from 'node:fs';

const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const expect = (condition, message) => { if (!condition) throw new Error(message); };

const floor = read('src/utils/tibiaFloors.ts');
const map = read('src/pages/TibiaMapPage.tsx');
const card = read('src/components/HuntZoneCard.tsx');
const cyclopedia = read('src/pages/CreaturesPage.tsx');
const metadata = read('src/components/MapMetadataPanel.tsx');
const planner = read('src/pages/HuntRecommendationsPage.tsx');

expect(floor.includes('7 - internalFloor'), 'Ground-floor display must remain a presentation-only z=7 -> floor 0 conversion.');
for (const layer of ["'hunt_zone'", "'creature'", "'boss'", "'item'", "'quest'", "'npc'", "'location'"]) {
  expect(read('src/services/tibiaMap.ts').includes(layer), `Universal map layer missing: ${layer}`);
}
expect(map.includes('locationNotMapped'), 'Map selections need an explicit unmapped state.');
expect(card.includes('LocalizedMapPreview'), 'Hunt Zone cards must use the localized canonical floor preview.');
expect(cyclopedia.includes('<HuntZoneCard'), 'Cyclopedia Hunt Zones must reuse the shared aligned card.');
expect(!cyclopedia.includes('getMapImageUrl(zone.id'), 'Cyclopedia cards must not reuse broad provider map fragments.');
expect(metadata.includes('Promise.allSettled') && metadata.includes('Nearby is optional'), 'Optional nearby failures must not erase authoritative spatial geometry.');
expect(planner.includes('loading || loadingMore || requestRef.current'), 'Planner infinite scroll must not replace ownership of an active recommendation request.');

console.log('Map/spatial guards passed.');
