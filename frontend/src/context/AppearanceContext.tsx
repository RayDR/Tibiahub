import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

export const THEME_IDS = ['medieval', 'tibia-stone', 'midnight-arcana', 'blood-moon', 'high-contrast'] as const;
export const MOTION_MODES = ['system', 'reduced', 'enhanced'] as const;
export const DENSITY_MODES = ['comfortable', 'compact'] as const;

export type ThemeId = (typeof THEME_IDS)[number];
export type MotionMode = (typeof MOTION_MODES)[number];
export type DensityMode = (typeof DENSITY_MODES)[number];

export interface AppearancePreferences {
  theme: ThemeId;
  motion: MotionMode;
  density: DensityMode;
}

export const APPEARANCE_STORAGE_KEY = 'tibiahub.appearance.v1';
const LEGACY_THEME_STORAGE_KEY = 'theme';
export const DEFAULT_APPEARANCE: AppearancePreferences = {
  theme: 'tibia-stone',
  motion: 'system',
  density: 'comfortable',
};

const includes = <T extends string>(values: readonly T[], value: unknown): value is T => (
  typeof value === 'string' && values.includes(value as T)
);

export const normalizeAppearancePreferences = (value: unknown): AppearancePreferences => {
  const candidate = value && typeof value === 'object' ? value as Partial<AppearancePreferences> : {};
  const storedTheme = (candidate as { theme?: unknown }).theme;
  const migratedTheme = storedTheme === 'default' ? 'tibia-stone' : storedTheme;
  return {
    theme: includes(THEME_IDS, migratedTheme) ? migratedTheme : DEFAULT_APPEARANCE.theme,
    motion: includes(MOTION_MODES, candidate.motion) ? candidate.motion : DEFAULT_APPEARANCE.motion,
    density: includes(DENSITY_MODES, candidate.density) ? candidate.density : DEFAULT_APPEARANCE.density,
  };
};

export const readAppearancePreferences = (): AppearancePreferences => {
  if (typeof window === 'undefined') return DEFAULT_APPEARANCE;
  try {
    const stored = window.localStorage.getItem(APPEARANCE_STORAGE_KEY);
    if (stored) return normalizeAppearancePreferences(JSON.parse(stored));
    const legacyTheme = window.localStorage.getItem(LEGACY_THEME_STORAGE_KEY);
    return normalizeAppearancePreferences({ theme: legacyTheme });
  } catch {
    return DEFAULT_APPEARANCE;
  }
};

export const applyAppearancePreferences = (preferences: AppearancePreferences): void => {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.dataset.theme = preferences.theme;
  root.dataset.motion = preferences.motion;
  root.dataset.density = preferences.density;
};

const persistAppearancePreferences = (preferences: AppearancePreferences): void => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(preferences));
    window.localStorage.removeItem(LEGACY_THEME_STORAGE_KEY);
  } catch {
    // Preferences remain active for this session when storage is unavailable.
  }
};

export const initializeAppearance = (): AppearancePreferences => {
  const preferences = readAppearancePreferences();
  applyAppearancePreferences(preferences);
  persistAppearancePreferences(preferences);
  return preferences;
};

interface AppearanceContextValue extends AppearancePreferences {
  setTheme: (theme: ThemeId) => void;
  setMotion: (motion: MotionMode) => void;
  setDensity: (density: DensityMode) => void;
  resetAppearance: () => void;
}

const AppearanceContext = createContext<AppearanceContextValue | null>(null);

interface AppearanceProviderProps {
  children: React.ReactNode;
  initialPreferences?: AppearancePreferences;
}

export const AppearanceProvider: React.FC<AppearanceProviderProps> = ({ children, initialPreferences }) => {
  const [preferences, setPreferences] = useState<AppearancePreferences>(() => initialPreferences ?? readAppearancePreferences());

  useEffect(() => {
    applyAppearancePreferences(preferences);
    persistAppearancePreferences(preferences);
  }, [preferences]);

  useEffect(() => {
    const syncPreferences = (event: StorageEvent) => {
      if (event.key === APPEARANCE_STORAGE_KEY) setPreferences(readAppearancePreferences());
    };
    window.addEventListener('storage', syncPreferences);
    return () => window.removeEventListener('storage', syncPreferences);
  }, []);

  const setTheme = useCallback((theme: ThemeId) => setPreferences((current) => ({ ...current, theme })), []);
  const setMotion = useCallback((motion: MotionMode) => setPreferences((current) => ({ ...current, motion })), []);
  const setDensity = useCallback((density: DensityMode) => setPreferences((current) => ({ ...current, density })), []);
  const resetAppearance = useCallback(() => setPreferences(DEFAULT_APPEARANCE), []);
  const value = useMemo(() => ({ ...preferences, setTheme, setMotion, setDensity, resetAppearance }), [preferences, setTheme, setMotion, setDensity, resetAppearance]);

  return <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>;
};

export const useAppearance = (): AppearanceContextValue => {
  const context = useContext(AppearanceContext);
  if (!context) throw new Error('useAppearance must be used within AppearanceProvider');
  return context;
};
