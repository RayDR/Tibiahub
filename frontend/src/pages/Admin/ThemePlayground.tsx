import { useState } from 'react';
import { Bell, Check, ChevronDown, Palette, Play, RotateCcw, Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  DENSITY_MODES,
  MOTION_MODES,
  THEME_IDS,
  useAppearance,
} from '../../context/AppearanceContext';
import {
  Alert,
  AppButton,
  AppTabs,
  Badge,
  Card,
  Dialog,
  Dropdown,
  EmptyState,
  FormField,
  Input,
  LoadingState,
  Panel,
  Section,
  Select,
  Skeleton,
  Table,
  TableContainer,
  Textarea,
  Toolbar,
} from '../../components/ui';

const tabItems = ['components', 'states', 'data'].map((key) => ({ key, label: key }));

export default function ThemePlayground() {
  const { t } = useTranslation();
  const { theme, motion, density, setTheme, setMotion, setDensity, resetAppearance } = useAppearance();
  const [activeTab, setActiveTab] = useState('components');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [motionPreview, setMotionPreview] = useState(0);
  const localizedTabs = tabItems.map((item) => ({ ...item, label: t(`themePlayground.tabs.${item.key}`) }));

  return (
    <div className="space-y-6">
      <Panel className="p-4 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary-subtle text-primary">
              <Palette className="size-5" aria-hidden="true" />
            </span>
            <div>
              <h1 className="text-xl font-semibold sm:text-2xl">{t('themePlayground.title')}</h1>
              <p className="mt-1 max-w-3xl text-sm text-content-secondary">{t('themePlayground.subtitle')}</p>
            </div>
          </div>
          <AppButton variant="secondary" size="sm" onClick={resetAppearance}>
            <RotateCcw className="size-4" aria-hidden="true" />
            {t('themePlayground.reset')}
          </AppButton>
        </div>
      </Panel>

      <Section aria-labelledby="theme-gallery-title">
        <div>
          <h2 id="theme-gallery-title" className="text-lg font-semibold">{t('themePlayground.gallery')}</h2>
          <p className="text-sm text-content-muted">{t('themePlayground.galleryHelp')}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {THEME_IDS.map((themeId) => {
            const selected = theme === themeId;
            return (
              <button
                type="button"
                key={themeId}
                data-theme={themeId}
                aria-pressed={selected}
                onClick={() => setTheme(themeId)}
                className={`ds-card min-h-36 overflow-hidden p-4 text-left transition-colors ${selected ? 'border-primary ring-2 ring-primary/30' : 'hover:border-line-strong'}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-content-primary">{t(`themes.${themeId}.name`)}</h3>
                    <p className="mt-1 text-xs text-content-secondary">{t(`themes.${themeId}.description`)}</p>
                  </div>
                  {selected ? <Check className="size-5 text-primary" aria-label={t('themePlayground.selected')} /> : null}
                </div>
                <div className="mt-5 grid grid-cols-6 gap-1.5" aria-hidden="true">
                  <span className="h-7 rounded-sm border border-line bg-surface-base" />
                  <span className="h-7 rounded-sm border border-line bg-surface-raised" />
                  <span className="h-7 rounded-sm bg-primary" />
                  <span className="h-7 rounded-sm bg-accent" />
                  <span className="h-7 rounded-sm bg-success" />
                  <span className="h-7 rounded-sm bg-danger" />
                </div>
              </button>
            );
          })}
        </div>
      </Section>

      <Panel className="grid gap-5 p-4 sm:p-6 lg:grid-cols-2">
        <PreferencePreview
          title={t('appearance.motion')}
          values={MOTION_MODES}
          selected={motion}
          onChange={setMotion}
          getLabel={(value) => t(`appearance.motionOptions.${value}`)}
        />
        <PreferencePreview
          title={t('appearance.density')}
          values={DENSITY_MODES}
          selected={density}
          onChange={setDensity}
          getLabel={(value) => t(`appearance.densityOptions.${value}`)}
        />
      </Panel>

      <AppTabs items={localizedTabs} activeKey={activeTab} onChange={setActiveTab} />

      {activeTab === 'components' ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="space-y-5 p-4 sm:p-6">
            <h2 className="text-lg font-semibold">{t('themePlayground.components.actions')}</h2>
            <Toolbar>
              <AppButton>{t('themePlayground.actions.primary')}</AppButton>
              <AppButton variant="secondary">{t('themePlayground.actions.secondary')}</AppButton>
              <AppButton variant="ghost">{t('themePlayground.actions.ghost')}</AppButton>
              <AppButton variant="danger">{t('themePlayground.actions.danger')}</AppButton>
              <AppButton disabled>{t('themePlayground.actions.disabled')}</AppButton>
            </Toolbar>
            <div className="flex flex-wrap gap-2">
              <Badge>{t('themePlayground.tones.neutral')}</Badge>
              <Badge tone="primary">{t('themePlayground.tones.primary')}</Badge>
              <Badge tone="success">{t('themePlayground.tones.success')}</Badge>
              <Badge tone="warning">{t('themePlayground.tones.warning')}</Badge>
              <Badge tone="danger">{t('themePlayground.tones.danger')}</Badge>
              <Badge tone="info">{t('themePlayground.tones.info')}</Badge>
            </div>
          </Card>

          <Card className="space-y-4 p-4 sm:p-6">
            <h2 className="text-lg font-semibold">{t('themePlayground.components.forms')}</h2>
            <FormField label={t('themePlayground.forms.name')} helpText={t('themePlayground.forms.help')}>
              <Input placeholder={t('themePlayground.forms.placeholder')} />
            </FormField>
            <FormField label={t('themePlayground.forms.category')}>
              <Select defaultValue="creature">
                <option value="creature">{t('themePlayground.forms.creature')}</option>
                <option value="quest">{t('themePlayground.forms.quest')}</option>
              </Select>
            </FormField>
            <FormField label={t('themePlayground.forms.notes')}>
              <Textarea placeholder={t('themePlayground.forms.notesPlaceholder')} />
            </FormField>
          </Card>

          <Card className="space-y-4 p-4 sm:p-6">
            <h2 className="text-lg font-semibold">{t('themePlayground.components.overlays')}</h2>
            <Toolbar>
              <AppButton variant="secondary" onClick={() => setDropdownOpen((value) => !value)} aria-expanded={dropdownOpen}>
                {t('themePlayground.dropdown.open')} <ChevronDown className="size-4" aria-hidden="true" />
              </AppButton>
              <AppButton onClick={() => setDialogOpen(true)}>{t('themePlayground.dialog.open')}</AppButton>
            </Toolbar>
            <div className="relative min-h-28">
              {dropdownOpen ? (
                <Dropdown className="absolute left-0 top-0">
                  {['profile', 'settings', 'signOut'].map((item) => (
                    <button type="button" role="menuitem" key={item} className="block w-full rounded-sm px-3 py-2 text-left text-sm text-content-secondary hover:bg-surface-hover hover:text-content-primary">
                      {t(`themePlayground.dropdown.${item}`)}
                    </button>
                  ))}
                </Dropdown>
              ) : <p className="text-sm text-content-muted">{t('themePlayground.dropdown.closed')}</p>}
            </div>
          </Card>

          <Card className="space-y-4 p-4 sm:p-6">
            <h2 className="text-lg font-semibold">{t('themePlayground.components.motion')}</h2>
            <AppButton variant="secondary" onClick={() => setMotionPreview((value) => value + 1)}>
              <Play className="size-4" aria-hidden="true" /> {t('themePlayground.motion.play')}
            </AppButton>
            <div key={motionPreview} className="ds-motion-preview rounded-lg border border-primary/40 bg-primary-subtle p-4">
              <Sparkles className="size-5 text-primary" aria-hidden="true" />
              <p className="mt-2 text-sm text-content-secondary">{t('themePlayground.motion.description', { mode: t(`appearance.motionOptions.${motion}`) })}</p>
            </div>
          </Card>
        </div>
      ) : null}

      {activeTab === 'states' ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="space-y-3 p-4 sm:p-6">
            <Alert tone="success">{t('themePlayground.alerts.success')}</Alert>
            <Alert tone="warning">{t('themePlayground.alerts.warning')}</Alert>
            <Alert tone="danger">{t('themePlayground.alerts.danger')}</Alert>
            <Alert tone="info">{t('themePlayground.alerts.info')}</Alert>
          </Card>
          <Card className="space-y-4 p-4 sm:p-6">
            <EmptyState icon={<Bell />} title={t('themePlayground.states.empty')} description={t('themePlayground.states.emptyHelp')} />
            <LoadingState title={t('themePlayground.states.loading')} />
            <div className="space-y-2"><Skeleton /><Skeleton className="w-4/5" /><Skeleton className="w-2/3" /></div>
          </Card>
        </div>
      ) : null}

      {activeTab === 'data' ? (
        <TableContainer>
          <Table>
            <thead><tr><th>{t('themePlayground.table.component')}</th><th>{t('themePlayground.table.state')}</th><th>{t('themePlayground.table.token')}</th></tr></thead>
            <tbody>
              <tr><td>{t('themePlayground.table.button')}</td><td><Badge tone="success">{t('themePlayground.table.ready')}</Badge></td><td><code>--primary</code></td></tr>
              <tr><td>{t('themePlayground.table.dialog')}</td><td><Badge tone="info">{t('themePlayground.table.layered')}</Badge></td><td><code>--z-modal</code></td></tr>
              <tr><td>{t('themePlayground.table.disabled')}</td><td><Badge>{t('themePlayground.table.visible')}</Badge></td><td><code>--disabled-surface</code></td></tr>
            </tbody>
          </Table>
        </TableContainer>
      ) : null}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} label={t('themePlayground.dialog.title')} className="p-5 sm:p-6">
        <h2 className="text-xl font-semibold">{t('themePlayground.dialog.title')}</h2>
        <p className="mt-2 text-sm text-content-secondary">{t('themePlayground.dialog.description')}</p>
        <div className="mt-5 flex justify-end"><AppButton onClick={() => setDialogOpen(false)}>{t('themePlayground.dialog.close')}</AppButton></div>
      </Dialog>
    </div>
  );
}

interface PreferencePreviewProps<T extends string> {
  title: string;
  values: readonly T[];
  selected: T;
  onChange: (value: T) => void;
  getLabel: (value: T) => string;
}

function PreferencePreview<T extends string>({ title, values, selected, onChange, getLabel }: PreferencePreviewProps<T>) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-semibold text-content-primary">{title}</legend>
      <div className="app-tablist" role="group">
        {values.map((value) => (
          <button type="button" key={value} className="app-tab min-w-0 flex-1 justify-center" data-active={selected === value} aria-pressed={selected === value} onClick={() => onChange(value)}>
            {getLabel(value)}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
