import { useState } from 'react';
import { Check, Contrast, Crown, Droplets, MoonStar, Mountain, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  DENSITY_MODES,
  MOTION_MODES,
  THEME_IDS,
  type DensityMode,
  type MotionMode,
  type ThemeId,
  useAppearance,
} from '../context/AppearanceContext';
import { Dropdown } from './ui';

const themeIcons = {
  medieval: Crown,
  'tibia-stone': Mountain,
  'midnight-arcana': MoonStar,
  'blood-moon': Droplets,
  'high-contrast': Contrast,
} as const;

export default function ThemeSwitcher() {
  const { t } = useTranslation();
  const { theme, motion, density, setTheme, setMotion, setDensity } = useAppearance();
  const [isOpen, setIsOpen] = useState(false);
  const CurrentIcon = themeIcons[theme];

  const selectTheme = (value: ThemeId) => {
    setTheme(value);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((value) => !value)}
        aria-label={t('appearance.open')}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls="appearance-menu"
        className="group flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-content-secondary transition-colors hover:bg-surface-hover hover:text-primary"
      >
        <CurrentIcon className="size-4 transition-transform group-hover:rotate-6" aria-hidden="true" />
        <span className="hidden text-xs font-medium md:inline">{t(`themes.${theme}.name`)}</span>
      </button>

      {isOpen ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-base cursor-default"
            onClick={() => setIsOpen(false)}
            aria-label={t('appearance.close')}
          />
          <Dropdown id="appearance-menu" className="absolute right-0 z-dropdown mt-2 max-h-[min(42rem,calc(100dvh-6rem))] w-[min(22rem,calc(100vw-1rem))] overflow-y-auto p-3">
            <div className="mb-3 flex items-center gap-2 border-b border-line pb-3">
              <Sparkles className="size-4 text-primary" aria-hidden="true" />
              <div>
                <p className="text-sm font-semibold text-content-primary">{t('appearance.title')}</p>
                <p className="text-xs text-content-muted">{t('appearance.persisted')}</p>
              </div>
            </div>

            <fieldset>
              <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-secondary">{t('appearance.theme')}</legend>
              <div className="grid gap-1 sm:grid-cols-2">
                {THEME_IDS.map((themeId) => {
                  const Icon = themeIcons[themeId];
                  const selected = theme === themeId;
                  return (
                    <button
                      type="button"
                      key={themeId}
                      onClick={() => selectTheme(themeId)}
                      aria-pressed={selected}
                      className={`flex min-h-11 items-center gap-2 rounded-md border px-2.5 py-2 text-left text-xs transition-colors ${selected ? 'border-primary bg-primary-subtle text-primary' : 'border-transparent text-content-secondary hover:border-line hover:bg-surface-hover hover:text-content-primary'}`}
                    >
                      <Icon className="size-4 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate">{t(`themes.${themeId}.name`)}</span>
                      {selected ? <Check className="size-3.5 shrink-0" aria-hidden="true" /> : null}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <PreferenceGroup
              label={t('appearance.motion')}
              values={MOTION_MODES}
              selected={motion}
              onChange={setMotion}
              getLabel={(value) => t(`appearance.motionOptions.${value}`)}
            />
            <PreferenceGroup
              label={t('appearance.density')}
              values={DENSITY_MODES}
              selected={density}
              onChange={setDensity}
              getLabel={(value) => t(`appearance.densityOptions.${value}`)}
            />
          </Dropdown>
        </>
      ) : null}
    </div>
  );
}

interface PreferenceGroupProps<T extends MotionMode | DensityMode> {
  label: string;
  values: readonly T[];
  selected: T;
  onChange: (value: T) => void;
  getLabel: (value: T) => string;
}

function PreferenceGroup<T extends MotionMode | DensityMode>({ label, values, selected, onChange, getLabel }: PreferenceGroupProps<T>) {
  return (
    <fieldset className="mt-4">
      <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-secondary">{label}</legend>
      <div className="app-tablist" role="group">
        {values.map((value) => (
          <button
            type="button"
            key={value}
            className="app-tab min-w-0 flex-1 justify-center px-2 text-xs"
            data-active={selected === value}
            aria-pressed={selected === value}
            onClick={() => onChange(value)}
          >
            {getLabel(value)}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
