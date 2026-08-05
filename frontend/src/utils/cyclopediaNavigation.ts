export const CYCLOPEDIA_RETURN_TARGET_KEY = 'tibiahub:cyclopedia:return-target';

const CYCLOPEDIA_PATH_PREFIX = '/cyclopedia';

export interface CyclopediaRouteState {
  from?: string;
  fromCyclopedia?: boolean;
}

export interface CyclopediaLocationState {
  tab: string;
  q?: string;
  selected?: string;
  category?: string;
  sort?: string;
  order?: string;
}

export function isCyclopediaPath(path: string | null | undefined): path is string {
  return typeof path === 'string' && path.startsWith(CYCLOPEDIA_PATH_PREFIX);
}

export function buildCyclopediaPath(state: CyclopediaLocationState): string {
  const params = new URLSearchParams();
  params.set('tab', state.tab);

  if (state.q?.trim()) params.set('q', state.q.trim());
  if (state.selected?.trim()) params.set('selected', state.selected.trim());
  if (state.category?.trim()) params.set('category', state.category.trim());
  if (state.sort?.trim()) params.set('sort', state.sort.trim());
  if (state.order?.trim()) params.set('order', state.order.trim());

  return `${CYCLOPEDIA_PATH_PREFIX}?${params.toString()}`;
}

export function createCyclopediaRouteState(from: string): CyclopediaRouteState {
  return { from, fromCyclopedia: true };
}

export function saveCyclopediaReturnTarget(path: string): void {
  if (!isCyclopediaPath(path)) return;

  try {
    sessionStorage.setItem(CYCLOPEDIA_RETURN_TARGET_KEY, path);
  } catch {
    // Ignore storage failures.
  }
}

export function loadCyclopediaReturnTarget(): string | null {
  try {
    const value = sessionStorage.getItem(CYCLOPEDIA_RETURN_TARGET_KEY);
    return isCyclopediaPath(value) ? value : null;
  } catch {
    return null;
  }
}

export function resolveCyclopediaReturnTarget(
  stateFrom: unknown,
  fallback: string,
): string {
  if (typeof stateFrom === 'string' && isCyclopediaPath(stateFrom)) {
    return stateFrom;
  }

  const stored = loadCyclopediaReturnTarget();
  if (stored) return stored;

  return fallback;
}
