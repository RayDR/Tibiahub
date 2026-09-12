import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const navigation = read('src/components/Navigation.tsx');
const language = read('src/components/LanguageSwitcher.tsx');
const theme = read('src/components/ThemeSwitcher.tsx');
const account = read('src/components/account/AccountMenu.tsx');
const globalSearch = read('src/components/search/GlobalCyclopediaSearch.tsx');
const presentation = read('src/styles/site-presentation.css');

assert.match(language, /createPortal/, 'Language dropdown must portal outside the backdrop-filter navbar containing block');
assert.match(theme, /createPortal/, 'Appearance dropdown must portal outside the backdrop-filter navbar containing block');
assert.match(theme, /menuRef\.current\?\.contains/, 'Appearance outside-click handling must treat the portaled menu as inside');

assert.match(navigation, /const compactLayout = layout === 'compact'/, 'Navigation must derive compact content mode from Appearance');
assert.match(navigation, /isAuthenticated && !compactLayout \? <CharacterSwitcher/, 'Standalone character selector must leave the compact navbar');
assert.match(navigation, /navbar_show_global_search && compactLayout \? <GlobalCyclopediaSearch compact/, 'Compact navbar must use icon-driven global search');
assert.match(navigation, /navbar_show_global_search && !compactLayout/, 'Wide layout must retain the full global search field');

assert.match(account, /useActiveCharacter/, 'Compact profile menu must own character context');
assert.match(account, /activeCharacter\?\.character_name \|\| user\.display_name/, 'Compact profile trigger must display the selected character name');
assert.match(account, /setCharactersOpen/, 'Compact profile menu must allow switching characters inline');

assert.match(globalSearch, /compact\?: boolean/, 'Global search must support a compact trigger mode');
assert.match(globalSearch, /Ctrl K/, 'Compact search must retain the keyboard shortcut affordance');
assert.match(globalSearch, /app-global-search-compact-panel/, 'Compact search must expand into a bounded panel');
assert.match(presentation, /width: clamp\(18rem, 42vw, 34rem\)/, 'Compact search panel must remain viewport-proportional');
assert.match(presentation, /max-height: min\(62dvh, 30rem\)/, 'Compact search results must remain vertically bounded');

console.log('Navigation overlay/compact checks passed.');
