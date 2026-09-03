import { useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Map, MapPin, Search, Swords, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import LocalizedMapPreview from '../map/LocalizedMapPreview';
import { Alert, Badge, FormField, Input } from '../ui';
import { huntZonesApi } from '../../services/api';
import type { GuildHuntZoneSummary } from '../../services/huntPlanner';
import { buildMapEntityUrl } from '../../services/tibiaMap';
import type { HuntZone } from '../../types';

export type CanonicalHuntZoneValue = HuntZone | GuildHuntZoneSummary;

interface Props {
  mode: 'canonical' | 'custom';
  value: CanonicalHuntZoneValue | null;
  disabled?: boolean;
  onModeChange: (mode: 'canonical' | 'custom') => void;
  onChange: (zone: CanonicalHuntZoneValue | null) => void;
}

const canonicalId = (zone: CanonicalHuntZoneValue) => zone.canonical_id || null;
const domainId = (zone: CanonicalHuntZoneValue) => 'id' in zone ? zone.id : zone.domain_id;

export default function CanonicalHuntZonePicker({ mode, value, disabled, onModeChange, onChange }: Props) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<HuntZone[]>([]);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const detailSequence = useRef(0);

  useEffect(() => {
    if (mode !== 'canonical' || value || disabled) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setFailed(false);
      void huntZonesApi.getAll({
        search: query.trim() || undefined,
        canonical_only: true,
        limit: 8,
      }, controller.signal).then((rows) => {
        setResults(rows.filter((row) => row.identity_state === 'canonical' && Boolean(row.canonical_id)));
        setActiveIndex(0);
      }).catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      }).finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [disabled, mode, query, value]);

  const select = (zone: HuntZone) => {
    if (!zone.canonical_id) return;
    onChange(zone);
    const sequence = ++detailSequence.current;
    void huntZonesApi.getByIdentifier(zone.id).then((detail) => {
      if (detailSequence.current === sequence && detail.canonical_id === zone.canonical_id) onChange(detail);
    }).catch(() => {
      // The bounded list projection remains a valid selection and preview.
    });
  };

  const setMode = (next: 'canonical' | 'custom') => {
    detailSequence.current += 1;
    if (next === 'custom') onChange(null);
    onModeChange(next);
  };

  return <section className="rounded-2xl border border-line bg-surface p-4" aria-labelledby="hunt-zone-picker-title">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 id="hunt-zone-picker-title" className="font-semibold">{t('huntPlanner.zone.title')}</h3>
        <p className="mt-1 text-sm text-content-secondary">{t('huntPlanner.zone.help')}</p>
      </div>
      <div className="inline-flex rounded-xl border border-line bg-surface-raised p-1" role="radiogroup" aria-label={t('huntPlanner.zone.modeLabel')}>
        {(['canonical', 'custom'] as const).map((option) => <button
          key={option}
          type="button"
          role="radio"
          aria-checked={mode === option}
          disabled={disabled}
          onClick={() => setMode(option)}
          className={`min-h-10 rounded-lg px-3 text-sm font-semibold ${mode === option ? 'bg-primary text-content-on-primary' : 'text-content-secondary hover:bg-surface'}`}
        >{t(`huntPlanner.zone.modes.${option}`)}</button>)}
      </div>
    </div>

    {mode === 'custom' ? <p className="mt-4 rounded-xl bg-surface-raised p-3 text-sm text-content-secondary">{t('huntPlanner.zone.customHelp')}</p> : value ? <SelectedZonePreview zone={value} onClear={() => { detailSequence.current += 1; onChange(null); }} disabled={disabled} /> : <div className="mt-4">
      <FormField label={t('huntPlanner.zone.searchLabel')}>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-content-muted" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex((index) => Math.min(results.length - 1, index + 1)); }
              if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex((index) => Math.max(0, index - 1)); }
              if (event.key === 'Enter' && results[activeIndex]) { event.preventDefault(); select(results[activeIndex]); }
              if (event.key === 'Escape') setResults([]);
            }}
            className="pl-9"
            placeholder={t('huntPlanner.zone.searchPlaceholder')}
            autoComplete="off"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={results.length > 0}
            aria-controls="canonical-hunt-zone-results"
            aria-activedescendant={results[activeIndex] ? `canonical-zone-${results[activeIndex].id}` : undefined}
            disabled={disabled}
          />
        </div>
      </FormField>
      <p className="mt-2 text-xs text-content-muted" aria-live="polite">
        {loading ? t('huntPlanner.zone.searching') : failed ? t('huntPlanner.zone.searchFailed') : t('huntPlanner.zone.resultCount', { count: results.length })}
      </p>
      {failed ? <Alert tone="danger" className="mt-3">{t('huntPlanner.zone.searchFailed')}</Alert> : null}
      {results.length > 0 ? <div id="canonical-hunt-zone-results" role="listbox" className="mt-3 grid gap-2">
        {results.map((zone, index) => <button
          id={`canonical-zone-${zone.id}`}
          key={zone.canonical_id || zone.id}
          type="button"
          role="option"
          aria-selected={activeIndex === index}
          onMouseEnter={() => setActiveIndex(index)}
          onClick={() => select(zone)}
          className={`flex min-h-14 items-center gap-3 rounded-xl border p-3 text-left ${activeIndex === index ? 'border-primary bg-primary-subtle' : 'border-line bg-surface-raised hover:border-primary/50'}`}
        >
          <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary-subtle text-primary"><Swords className="size-5" /></span>
          <span className="min-w-0 flex-1">
            <strong className="block truncate text-sm text-content-primary">{zone.name}</strong>
            <span className="block truncate text-xs text-content-secondary">{zone.region || zone.city || t('huntPlanner.zone.locationUnknown')}</span>
          </span>
          {zone.min_level != null ? <Badge tone="info">{t('huntPlanner.zone.level', { level: zone.min_level })}</Badge> : null}
        </button>)}
      </div> : null}
    </div>}
  </section>;
}

function SelectedZonePreview({ zone, onClear, disabled }: { zone: CanonicalHuntZoneValue; onClear: () => void; disabled?: boolean }) {
  const { t } = useTranslation();
  const full = 'id' in zone ? zone : null;
  const summary = 'domain_id' in zone ? zone : null;
  const creatures = zone.creature_preview || [];
  const quests = full?.access?.quests?.filter((quest) => quest.requirement_type === 'required_for_access' || quest.requirement_type === 'unlocks_access')
    || summary?.access_quests
    || (full?.access_required && full.quest_name ? [{ id: full.quest_id || undefined, name: full.quest_name, slug: full.quest_slug }] : []);
  const mapAvailable = summary?.map_available || full?.spatial?.geometry_status === 'mapped';
  const mapFloor = summary?.map_floor ?? full?.spatial?.z;
  const id = canonicalId(zone);
  const detailsIdentifier = zone.slug || domainId(zone);
  const mediaUrl = summary?.media_url || (full?.representative_media?.status === 'available' ? full.representative_media.url : null);
  const isCurrent = summary?.is_current !== false;
  const mapUrl = buildMapEntityUrl({ canonicalEntityId: id, entityType: 'hunt_zone', name: zone.name, slug: zone.slug, floor: mapFloor });

  const metadata = useMemo(() => [
    zone.min_level != null ? t('huntPlanner.zone.level', { level: zone.min_level }) : null,
    zone.difficulty || null,
    zone.recommended_vocations?.length ? zone.recommended_vocations.join(' · ') : null,
  ].filter(Boolean), [t, zone.difficulty, zone.min_level, zone.recommended_vocations]);

  return <div className="mt-4 overflow-hidden rounded-2xl border border-primary/30 bg-surface-raised">
    <div className="grid sm:grid-cols-[9rem_1fr]">
      <div className="relative min-h-28 overflow-hidden bg-primary-subtle">
        {mediaUrl ? <img src={mediaUrl} alt="" className="absolute inset-0 size-full object-cover" />
          : mapAvailable && full?.spatial ? <LocalizedMapPreview spatial={full.spatial} label={t('huntPlanner.zone.mapPreview', { name: zone.name })} className="absolute inset-0" />
            : <span className="absolute inset-0 grid place-items-center text-primary"><Swords className="size-10" /></span>}
      </div>
      <div className="min-w-0 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Badge tone="info">{t('huntPlanner.zone.canonicalBadge')}</Badge>
            <h4 className="mt-2 truncate text-lg font-semibold">{zone.name}</h4>
            <p className="mt-1 flex items-start gap-1 text-sm text-content-secondary"><MapPin className="mt-0.5 size-4 shrink-0" />{zone.region || zone.city || t('huntPlanner.zone.locationUnknown')}</p>
          </div>
          <button type="button" onClick={onClear} disabled={disabled} className="app-button-ghost app-button-sm" aria-label={t('huntPlanner.zone.clear')}><X className="size-4" /></button>
        </div>
        {metadata.length ? <p className="mt-3 text-xs text-content-muted">{metadata.join(' · ')}</p> : null}
      </div>
    </div>
    {!isCurrent ? <Alert tone="warning" className="m-4 mt-0">{t('huntPlanner.zone.notCurrent')}</Alert> : null}
    {creatures.length > 0 ? <div className="border-t border-line p-4">
      <div className="flex items-center justify-between gap-2"><h5 className="text-sm font-semibold">{t('huntPlanner.zone.creatures')}</h5><span className="text-xs text-content-muted">{t('huntPlanner.zone.creatureCount', { count: zone.creature_count || creatures.length })}</span></div>
      <div className="mt-3 flex flex-wrap gap-2">{creatures.slice(0, 4).map((creature) => <span key={creature.canonical_id || creature.id || creature.name} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-line bg-surface px-2 py-1 text-xs">
        {creature.image_url ? <img src={creature.image_url} alt="" className="size-8 object-contain [image-rendering:pixelated]" /> : <Swords className="size-4 text-content-muted" />}
        <span>{creature.name}</span>{creature.is_boss ? <Badge tone="warning">{t('huntPlanner.zone.boss')}</Badge> : null}
      </span>)}</div>
      {(zone.creature_count || 0) > 4 && detailsIdentifier ? <Link to={`/hunt-zones/${detailsIdentifier}`} className="mt-3 inline-flex text-xs font-semibold text-primary hover:underline">{t('huntPlanner.zone.viewAllCreatures', { count: zone.creature_count })}</Link> : null}
    </div> : null}
    {zone.access_required === true ? <div className="border-t border-line bg-warning-subtle p-4">
      <p className="text-sm font-semibold text-warning"><BookOpen className="mr-2 inline size-4" />{t('huntPlanner.zone.accessRequired')}</p>
      {quests.length ? <div className="mt-2 flex flex-wrap gap-2">{quests.map((quest) => quest.slug || quest.id ? <Link key={quest.canonical_id || quest.id || quest.name} to={`/quests/${quest.slug || quest.id}`} className="app-button-secondary app-button-sm">{quest.name}</Link> : <span key={quest.name} className="text-sm text-content-secondary">{quest.name}</span>)}</div>
        : <p className="mt-2 text-sm text-content-secondary">{t('huntPlanner.zone.accessUnresolved')}</p>}
    </div> : zone.access_required == null ? <p className="border-t border-line p-4 text-sm text-content-muted">{t('huntPlanner.zone.accessUnknown')}</p> : null}
    <div className="flex flex-wrap gap-2 border-t border-line p-4">
      {detailsIdentifier ? <Link to={`/hunt-zones/${detailsIdentifier}`} className="app-button-secondary app-button-sm"><Swords className="size-4" />{t('huntPlanner.zone.details')}</Link> : null}
      {mapAvailable ? <Link to={mapUrl} className="app-button-secondary app-button-sm"><Map className="size-4" />{t('huntPlanner.zone.viewMap')}</Link>
        : <span className="inline-flex items-center gap-2 text-sm text-content-muted"><Map className="size-4" />{t('huntPlanner.zone.noGeometry')}</span>}
    </div>
  </div>;
}
