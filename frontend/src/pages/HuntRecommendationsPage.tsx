import {
  Bookmark,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Coins,
  Gauge,
  LayoutGrid,
  List,
  Map,
  Plus,
  RotateCcw,
  Scroll,
  Shield,
  Sparkles,
  Swords,
  Trash2,
  Trophy,
  User,
  Users,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import BrandCategoryFallbackIcon from '../components/icons/BrandCategoryFallbackIcon';
import HuntZonePreviewPanel from '../components/cyclopedia/HuntZonePreviewPanel';
import AppButton from '../components/ui/AppButton';
import AppInput from '../components/ui/AppInput';
import PageHeader from '../components/ui/PageHeader';
import { Page } from '../components/ui';
import { useActiveCharacter } from '../context/ActiveCharacterContext';
import { useAuth } from '../context/AuthContext';
import { activityApi } from '../services/activity';
import { huntZonesApi, tibiaApi } from '../services/api';
import type { HuntZoneSpatial } from '../types';
import { faCompass } from '@fortawesome/free-solid-svg-icons';

const VOCATIONS = [
  { id: 'knight', icon: Shield },
  { id: 'paladin', icon: Swords },
  { id: 'sorcerer', icon: Zap },
  { id: 'druid', icon: Sparkles },
  { id: 'monk', icon: Scroll },
] as const;

const PAGE_SIZE = 12;
const SEARCH_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const SESSION_KEY = 'tibiahub:hunt-planner:last-search:v3';

type PlannerMode = 'solo' | 'party';
type PlannerGoal = 'exp' | 'profit' | 'balanced';
type PlannerSort = 'match' | 'exp' | 'profit';

interface PartyMember {
  id: number;
  vocation: string;
  level: number;
}

interface CreaturePreview {
  id: number;
  name: string;
  slug?: string;
  image_url: string;
  hitpoints: number | null;
  experience: number | null;
  max_damage?: number;
  weaknesses: string[];
  resistances: string[];
  valuable_loot: Array<{ name: string; value: number; image_url?: string }>;
}

interface RecommendationItem {
  zone_id: number;
  zone_name: string;
  zone_slug?: string;
  score: number;
  min_level?: number | null;
  max_level?: number | null;
  suggested_level?: number | null;
  avg_exp_hour?: number;
  avg_profit_hour?: number;
  raw_creature_exp?: number | null;
  requires_premium?: boolean | null;
  requires_quest?: boolean | null;
  quest_name?: string;
  city?: string;
  region?: string;
  size?: string;
  difficulty?: string;
  danger?: string;
  location_z?: number;
  spatial?: HuntZoneSpatial | null;
  creatures?: CreaturePreview[];
}

interface RecommendationResponse {
  recommendations: RecommendationItem[];
  has_more: boolean;
  skip: number;
  limit: number;
  avg_level?: number;
  party_size?: number;
}

interface PlannerSearchSnapshot {
  version: 3;
  savedAt: string;
  mode: PlannerMode;
  soloVocation: string;
  minLevel: number;
  maxLevel: number;
  party: Array<{ vocation: string; level: number }>;
  goal: PlannerGoal;
  durationHours: number;
  budget: number | null;
  sort: PlannerSort;
  highlightBoosted: boolean;
}

const clampLevel = (value: number) => Math.min(2000, Math.max(8, Math.round(value || 8)));

const compactNumber = (value?: number | null) => {
  if (!value) return '—';
  return new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
};

const matchPercent = (score: number) => {
  const normalized = score <= 1 ? score * 100 : score;
  return Math.max(0, Math.min(100, Math.round(normalized)));
};

const riskKey = (value?: string | null): 'low' | 'medium' | 'high' => {
  const normalized = String(value || '').toLowerCase();
  if (/hard|high|danger|deadly|extreme|challeng/.test(normalized)) return 'high';
  if (/low|easy|safe|beginner|trivial/.test(normalized)) return 'low';
  return 'medium';
};

const isSnapshotFresh = (savedAt: string) => {
  const timestamp = new Date(savedAt).getTime();
  return Number.isFinite(timestamp) && Date.now() - timestamp <= SEARCH_TTL_MS;
};

const snapshotFromActivity = (entry: { created_at: string; metadata?: Record<string, any> | null }) => {
  const raw = entry.metadata?.planner_config as PlannerSearchSnapshot | undefined;
  if (!raw || raw.version !== 3) return null;
  const savedAt = raw.savedAt || entry.created_at;
  return isSnapshotFresh(savedAt) ? { ...raw, savedAt } : null;
};

export default function HuntRecommendationsPage() {
  const { t, i18n } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { activeCharacterId } = useActiveCharacter();
  const [searchParams] = useSearchParams();
  const preferredZone = searchParams.get('zone') || undefined;
  const isSpanish = i18n.language.startsWith('es');

  const copy = useMemo(() => isSpanish ? {
    setup: 'Configuración', reset: 'Restablecer', targetRange: 'Rango de nivel objetivo', duration: 'Duración', budget: 'Presupuesto (opcional)', priority: 'Prioridad', find: 'Buscar hunts', scouting: 'Buscando…',
    recommended: 'Recomendadas', compare: 'Comparar', mapView: 'Mapa', saved: 'Planes guardados', showing: 'Mostrando', recommendedHunts: 'hunts recomendadas', sort: 'Ordenar', bestOverall: 'Mejor resultado', bestXp: 'Más EXP', bestProfit: 'Más ganancia',
    huntLocation: 'Zona', recommendedFor: 'Recomendado para', risk: 'Riesgo', match: 'Match', preview: 'Selecciona una hunt para ver el preview', schedule: 'Plan de sesión', today: 'Hoy', break: 'Descanso', session: 'sesión',
    savedCharacter: 'La última búsqueda se guarda 7 días para el personaje activo.', savedSession: 'La última búsqueda se guarda 7 días en esta sesión.', restored: 'Búsqueda anterior restaurada.', highlightBoosted: 'Priorizar hunts con boosted', planningBudget: 'Solo se conserva como dato del plan; no altera el ranking hasta contar con costos de supplies documentados.',
  } : {
    setup: 'Planner Setup', reset: 'Reset', targetRange: 'Target Level Range', duration: 'Hunt Duration', budget: 'Budget (optional)', priority: 'Priority', find: 'Find Hunts', scouting: 'Scouting…',
    recommended: 'Recommended', compare: 'Compare', mapView: 'Map View', saved: 'Saved Plans', showing: 'Showing', recommendedHunts: 'recommended hunts', sort: 'Sort by', bestOverall: 'Best overall', bestXp: 'Most XP', bestProfit: 'Most profit',
    huntLocation: 'Hunt Location', recommendedFor: 'Recommended For', risk: 'Risk', match: 'Match', preview: 'Select a hunt to open its preview', schedule: 'Hunt Schedule', today: 'Today', break: 'Break', session: 'session',
    savedCharacter: 'The last search is retained for 7 days for the active character.', savedSession: 'The last search is retained for 7 days in this session.', restored: 'Previous search restored.', highlightBoosted: 'Prioritize hunts with boosted creatures', planningBudget: 'Stored with the plan only; it does not affect ranking until documented supply-cost data is available.',
  }, [isSpanish]);

  const [mode, setMode] = useState<PlannerMode>('solo');
  const [soloVocation, setSoloVocation] = useState('knight');
  const [minLevel, setMinLevel] = useState(100);
  const [maxLevel, setMaxLevel] = useState(200);
  const [party, setParty] = useState<PartyMember[]>([{ id: 1, vocation: 'knight', level: 100 }]);
  const [goal, setGoal] = useState<PlannerGoal>('balanced');
  const [durationHours, setDurationHours] = useState(2);
  const [budget, setBudget] = useState<number | null>(null);
  const [sort, setSort] = useState<PlannerSort>('match');
  const [highlightBoosted, setHighlightBoosted] = useState(true);
  const [boostedNames, setBoostedNames] = useState<string[]>([]);

  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<RecommendationItem | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [restored, setRestored] = useState(false);

  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  const effectiveSoloLevel = useMemo(
    () => clampLevel((clampLevel(minLevel) + clampLevel(maxLevel)) / 2),
    [maxLevel, minLevel],
  );

  const resetPlanner = useCallback(() => {
    setMode('solo');
    setSoloVocation('knight');
    setMinLevel(100);
    setMaxLevel(200);
    setParty([{ id: Date.now(), vocation: 'knight', level: 100 }]);
    setGoal('balanced');
    setDurationHours(2);
    setBudget(null);
    setSort('match');
    setHighlightBoosted(true);
    setRestored(false);
  }, []);

  const applySnapshot = useCallback((snapshot: PlannerSearchSnapshot) => {
    setMode(snapshot.mode);
    setSoloVocation(snapshot.soloVocation || 'knight');
    setMinLevel(clampLevel(snapshot.minLevel));
    setMaxLevel(clampLevel(snapshot.maxLevel));
    setParty((snapshot.party?.length ? snapshot.party : [{ vocation: 'knight', level: 100 }]).slice(0, 4).map((member, index) => ({
      id: Date.now() + index,
      vocation: member.vocation,
      level: clampLevel(member.level),
    })));
    setGoal(snapshot.goal || 'balanced');
    setDurationHours(Math.min(8, Math.max(1, Number(snapshot.durationHours) || 2)));
    setBudget(snapshot.budget == null ? null : Math.max(0, Number(snapshot.budget) || 0));
    setSort(snapshot.sort || 'match');
    setHighlightBoosted(snapshot.highlightBoosted !== false);
    setRestored(true);
  }, []);

  const currentSnapshot = useCallback((): PlannerSearchSnapshot => ({
    version: 3,
    savedAt: new Date().toISOString(),
    mode,
    soloVocation,
    minLevel: clampLevel(minLevel),
    maxLevel: clampLevel(maxLevel),
    party: party.map(({ vocation, level }) => ({ vocation, level: clampLevel(level) })),
    goal,
    durationHours,
    budget,
    sort,
    highlightBoosted,
  }), [budget, durationHours, goal, highlightBoosted, maxLevel, minLevel, mode, party, soloVocation, sort]);

  const request = useCallback(async (skip: number, signal: AbortSignal): Promise<RecommendationResponse> => (
    mode === 'solo'
      ? huntZonesApi.getRecommendations(
          soloVocation as never,
          effectiveSoloLevel,
          PAGE_SIZE,
          goal,
          preferredZone,
          skip,
          signal,
        )
      : huntZonesApi.getPartyRecommendations(
          party.map(({ vocation, level }) => ({ vocation, level: clampLevel(level) })),
          goal,
          PAGE_SIZE,
          skip,
          signal,
        )
  ), [effectiveSoloLevel, goal, mode, party, preferredZone, soloVocation]);

  const persistSearch = useCallback(async () => {
    const snapshot = currentSnapshot();
    if (isAuthenticated) {
      await activityApi.record({
        activity_type: 'hunt_search',
        entity_type: mode,
        query: mode === 'solo'
          ? `${soloVocation}:${effectiveSoloLevel}`
          : `party:${party.length}`,
        metadata: { planner_config: snapshot },
      });
      return;
    }

    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(snapshot));
    } catch {
      // Session persistence is optional when browser storage is unavailable.
    }
  }, [currentSnapshot, effectiveSoloLevel, isAuthenticated, mode, party.length, soloVocation]);

  const findSpots = useCallback(async (persist = true) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setLoadingMore(false);
    setError(false);

    try {
      const next = await request(0, controller.signal);
      if (!mountedRef.current || controller.signal.aborted) return;
      setData(next);
      setSelected(next.recommendations?.[0] || null);
      if (persist) void persistSearch().catch(() => undefined);
    } catch {
      if (mountedRef.current && !controller.signal.aborted) {
        setError(true);
        setData(null);
        setSelected(null);
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        if (mountedRef.current) setLoading(false);
      }
    }
  }, [persistSearch, request]);

  const loadMore = useCallback(async () => {
    if (!data?.has_more || loading || loadingMore || requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setLoadingMore(true);
    try {
      const next = await request(data.recommendations.length, controller.signal);
      if (mountedRef.current && !controller.signal.aborted) {
        setData({ ...next, recommendations: [...data.recommendations, ...next.recommendations] });
      }
    } catch {
      if (mountedRef.current && !controller.signal.aborted) setError(true);
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        if (mountedRef.current) setLoadingMore(false);
      }
    }
  }, [data, loading, loadingMore, request]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void tibiaApi.getBoosted(controller.signal)
      .then((result) => {
        const values = [result.creature.name, result.boss.name]
          .filter((value): value is string => Boolean(value?.trim()))
          .map((value) => value.toLowerCase());
        setBoostedNames(values);
      })
      .catch(() => setBoostedNames([]));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setHydrated(false);
    setRestored(false);

    const hydrate = async () => {
      if (isAuthenticated) {
        try {
          const activity = await activityApi.getMine(40, controller.signal, activeCharacterId);
          if (!active) return;
          const latest = activity.find((entry) => entry.activity_type === 'hunt_search');
          const snapshot = latest ? snapshotFromActivity(latest) : null;
          if (snapshot) applySnapshot(snapshot);
          else resetPlanner();
        } catch {
          if (active) resetPlanner();
        }
      } else {
        try {
          const raw = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null') as PlannerSearchSnapshot | null;
          if (raw && raw.version === 3 && isSnapshotFresh(raw.savedAt)) applySnapshot(raw);
          else {
            sessionStorage.removeItem(SESSION_KEY);
            resetPlanner();
          }
        } catch {
          resetPlanner();
        }
      }
      if (active) setHydrated(true);
    };

    void hydrate();
    return () => {
      active = false;
      controller.abort();
    };
  }, [activeCharacterId, applySnapshot, isAuthenticated, resetPlanner]);

  useEffect(() => {
    if (hydrated) void findSpots(false);
  }, [hydrated]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return undefined;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) void loadMore();
    }, { rootMargin: '260px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [loadMore]);

  const addMember = () => {
    if (party.length >= 4) return;
    setParty([...party, { id: Date.now(), vocation: 'druid', level: effectiveSoloLevel }]);
  };

  const isBoostedRecommendation = useCallback((item: RecommendationItem) => (
    Boolean(item.creatures?.some((creature) => boostedNames.includes(creature.name.toLowerCase())))
  ), [boostedNames]);

  const sortedRecommendations = useMemo(() => {
    const items = [...(data?.recommendations || [])];
    const metric = (item: RecommendationItem) => {
      if (sort === 'exp') return item.avg_exp_hour || 0;
      if (sort === 'profit') return item.avg_profit_hour || 0;
      return matchPercent(item.score);
    };
    return items.sort((left, right) => {
      if (highlightBoosted) {
        const boostDelta = Number(isBoostedRecommendation(right)) - Number(isBoostedRecommendation(left));
        if (boostDelta) return boostDelta;
      }
      return metric(right) - metric(left);
    });
  }, [data?.recommendations, highlightBoosted, isBoostedRecommendation, sort]);

  const maxExp = useMemo(() => Math.max(1, ...sortedRecommendations.map((item) => item.avg_exp_hour || 0)), [sortedRecommendations]);
  const maxProfit = useMemo(() => Math.max(1, ...sortedRecommendations.map((item) => item.avg_profit_hour || 0)), [sortedRecommendations]);

  const recommendedFor = (item: RecommendationItem) => {
    const range = item.min_level
      ? `Lv. ${item.min_level}${item.max_level ? `–${item.max_level}` : '+'}`
      : mode === 'solo'
        ? `Lv. ${minLevel}–${maxLevel}`
        : `${party.length} players`;
    return mode === 'solo'
      ? `${range} · ${t(`plannerRecovery.vocations.${soloVocation}`)}`
      : `${range} · ${party.length} players`;
  };

  const selectedIdentifier = selected ? String(selected.zone_slug || selected.zone_id) : null;

  return (
    <Page className="hunt-planner-page space-y-4">
      <section className="hunt-planner-hero">
        <div className="hunt-planner-hero__content">
          <div>
            <PageHeader title={t('plannerRecovery.title')} subtitle={t('plannerRecovery.subtitle')} icon={faCompass} size="md" />
          </div>
          <p className="hunt-planner-hero__motto">Plan hunts<br />gain progress<br />live greater adventures</p>
        </div>
      </section>

      <div className="hunt-planner-workspace">
        <aside className="hunt-planner-setup hunt-planner-panel" aria-label={copy.setup}>
          <header className="hunt-planner-setup__header">
            <h2 className="hunt-planner-section-title"><LayoutGrid className="size-4 text-primary" />{copy.setup}</h2>
            <button type="button" className="hunt-planner-reset" onClick={resetPlanner}><RotateCcw className="size-3.5" />{copy.reset}</button>
          </header>

          <div className="hunt-planner-setup__body">
            <div className="hunt-planner-mode-switch">
              <button type="button" className="hunt-planner-segment" data-active={mode === 'solo'} onClick={() => setMode('solo')}><User className="mr-1 inline size-3.5" />{t('plannerRecovery.solo')}</button>
              <button type="button" className="hunt-planner-segment" data-active={mode === 'party'} onClick={() => setMode('party')}><Users className="mr-1 inline size-3.5" />{t('plannerRecovery.party')}</button>
            </div>

            {mode === 'solo' ? (
              <>
                <div className="hunt-planner-field">
                  <span className="hunt-planner-field__label">{copy.targetRange}</span>
                  <div className="hunt-planner-level-row">
                    <AppInput type="number" min={8} max={2000} value={minLevel} onChange={(event) => setMinLevel(clampLevel(Number(event.target.value)))} aria-label={`${copy.targetRange} minimum`} />
                    <span className="text-content-muted">–</span>
                    <AppInput type="number" min={8} max={2000} value={maxLevel} onChange={(event) => setMaxLevel(clampLevel(Number(event.target.value)))} aria-label={`${copy.targetRange} maximum`} />
                  </div>
                  <div className="hunt-planner-level-track" aria-hidden="true" />
                </div>

                <div className="hunt-planner-field">
                  <label htmlFor="planner-vocation">{t('plannerRecovery.vocation')}</label>
                  <select id="planner-vocation" className="app-input" value={soloVocation} onChange={(event) => setSoloVocation(event.target.value)}>
                    {VOCATIONS.map(({ id }) => <option key={id} value={id}>{t(`plannerRecovery.vocations.${id}`)}</option>)}
                  </select>
                </div>
              </>
            ) : (
              <div className="hunt-planner-field">
                <span className="hunt-planner-field__label">{t('plannerRecovery.composition')}</span>
                <div className="hunt-planner-party-list">
                  {party.map((member, index) => (
                    <div key={member.id} className="hunt-planner-party-member">
                      <span className="text-xs text-content-muted">{index + 1}</span>
                      <select value={member.vocation} onChange={(event) => setParty(party.map((row) => row.id === member.id ? { ...row, vocation: event.target.value } : row))} className="app-input">
                        {VOCATIONS.map(({ id }) => <option key={id} value={id}>{t(`plannerRecovery.vocations.${id}`)}</option>)}
                      </select>
                      <input type="number" min={8} max={2000} value={member.level} onChange={(event) => setParty(party.map((row) => row.id === member.id ? { ...row, level: clampLevel(Number(event.target.value)) } : row))} aria-label={t('plannerRecovery.level')} className="app-input" />
                      <button type="button" disabled={party.length === 1} onClick={() => setParty(party.filter((row) => row.id !== member.id))} aria-label={t('plannerRecovery.removeMember')} className="text-content-muted hover:text-danger disabled:opacity-30"><Trash2 className="size-4" /></button>
                    </div>
                  ))}
                  <button type="button" disabled={party.length >= 4} onClick={addMember} className="app-button-secondary app-button-sm w-full"><Plus className="size-4" />{t('plannerRecovery.addMember')}</button>
                </div>
              </div>
            )}

            <div className="hunt-planner-field">
              <label htmlFor="planner-duration">{copy.duration}</label>
              <select id="planner-duration" className="app-input" value={durationHours} onChange={(event) => setDurationHours(Number(event.target.value))}>
                {[1, 2, 3, 4, 6, 8].map((hours) => <option key={hours} value={hours}>{hours} {hours === 1 ? 'hour' : 'hours'}</option>)}
              </select>
            </div>

            <div className="hunt-planner-field">
              <label htmlFor="planner-budget">{copy.budget}</label>
              <div className="relative">
                <Coins className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-primary" />
                <input id="planner-budget" className="app-input w-full pl-9" type="number" min={0} step={10000} value={budget ?? ''} onChange={(event) => setBudget(event.target.value ? Math.max(0, Number(event.target.value)) : null)} placeholder="500000" title={copy.planningBudget} />
              </div>
            </div>

            <div className="hunt-planner-field">
              <span className="hunt-planner-field__label">{copy.priority}</span>
              <div className="hunt-planner-priority">
                {(['exp', 'balanced', 'profit'] as const).map((item) => (
                  <button key={item} type="button" className="hunt-planner-segment" data-active={goal === item} onClick={() => setGoal(item)}>{t(`plannerRecovery.goals.${item}`)}</button>
                ))}
              </div>
            </div>

            <label className="hunt-planner-check">
              <input type="checkbox" checked={highlightBoosted} onChange={(event) => setHighlightBoosted(event.target.checked)} />
              <span>{copy.highlightBoosted}</span>
            </label>

            <AppButton onClick={() => void findSpots(true)} disabled={loading || !hydrated} className="hunt-planner-find">
              <Map className="size-4" />{loading ? copy.scouting : copy.find}
            </AppButton>

            <p className="hunt-planner-restore-note">
              <Clock3 className="size-3.5 shrink-0" />
              {restored ? `${copy.restored} ` : ''}{isAuthenticated ? copy.savedCharacter : copy.savedSession}
            </p>
          </div>
        </aside>

        <main className="hunt-planner-center">
          <div className="hunt-planner-toolbar">
            <div className="hunt-planner-toolbar__tabs">
              <button type="button" className="hunt-planner-toolbar__tab" data-active="true"><Trophy className="size-4" />{copy.recommended}</button>
              <button type="button" className="hunt-planner-toolbar__tab" disabled title="Comparison workflow will use selected recommendations"><Gauge className="size-4" />{copy.compare}</button>
              <button type="button" className="hunt-planner-toolbar__tab" disabled title="Use the selected hunt preview or open the full map"><Map className="size-4" />{copy.mapView}</button>
              <button type="button" className="hunt-planner-toolbar__tab" disabled title="Saved-plan persistence is not enabled yet"><Bookmark className="size-4" />{copy.saved}</button>
            </div>
            <div className="hunt-planner-toolbar__summary">
              <span>{copy.showing} <strong className="text-content-primary">{sortedRecommendations.length}</strong> {copy.recommendedHunts}</span>
              <label className="sr-only" htmlFor="planner-sort">{copy.sort}</label>
              <select id="planner-sort" className="app-input" value={sort} onChange={(event) => setSort(event.target.value as PlannerSort)}>
                <option value="match">{copy.bestOverall}</option>
                <option value="exp">{copy.bestXp}</option>
                <option value="profit">{copy.bestProfit}</option>
              </select>
              <List className="size-4 text-primary" aria-hidden="true" />
            </div>
          </div>

          <section className="hunt-planner-results" aria-label={copy.recommended}>
            <div className="hunt-planner-results__head" aria-hidden="true">
              <span>#</span><span>{copy.huntLocation}</span><span>{copy.recommendedFor}</span><span>XP / Hour</span><span>Profit / Hour</span><span>{copy.risk}</span><span>{copy.match}</span>
            </div>

            {error ? <div role="alert" className="hunt-planner-empty text-danger">{t('plannerRecovery.error')}</div> : null}
            {!loading && !error && sortedRecommendations.length === 0 ? <div className="hunt-planner-empty">{t('plannerRecovery.empty')}</div> : null}

            {sortedRecommendations.map((item, index) => {
              const boosted = isBoostedRecommendation(item);
              const risk = riskKey(item.danger || item.difficulty);
              const match = matchPercent(item.score);
              const firstCreature = item.creatures?.[0];
              return (
                <button
                  key={item.zone_id}
                  type="button"
                  className="hunt-planner-result"
                  data-selected={selected?.zone_id === item.zone_id}
                  onClick={() => setSelected(item)}
                  aria-label={`${item.zone_name}, ${match}% match`}
                >
                  <span className="hunt-planner-result__rank">{index + 1}</span>
                  <span className="hunt-planner-result__zone">
                    <span className="hunt-planner-result__sprite">
                      {firstCreature?.image_url ? <img src={firstCreature.image_url} alt="" /> : <BrandCategoryFallbackIcon category="zones" className="size-8 text-primary" />}
                    </span>
                    <span className="min-w-0">
                      <span className="hunt-planner-result__name">{item.zone_name}{boosted ? <span className="ml-2 rounded-full border border-accent/50 bg-accent/10 px-1.5 py-0.5 text-[0.58rem] font-bold uppercase text-accent">Boosted</span> : null}</span>
                      <span className="hunt-planner-result__place">{[item.city, item.region].filter(Boolean).join(' · ') || t('common.unknown')}</span>
                    </span>
                  </span>
                  <span className="hunt-planner-result__recommended">{recommendedFor(item)}</span>
                  <Metric value={item.avg_exp_hour} max={maxExp} />
                  <Metric value={item.avg_profit_hour} max={maxProfit} profit />
                  <span><span className="hunt-planner-risk" data-risk={risk}>{item.danger || item.difficulty || risk}</span></span>
                  <Metric value={match} max={100} match suffix="%" />
                </button>
              );
            })}

            <div ref={sentinelRef} className="h-1" aria-hidden="true" />
            {loadingMore ? <p className="p-3 text-center text-xs text-content-muted">{t('plannerRecovery.loadingMore')}</p> : null}
          </section>

          <section className="hunt-planner-panel hunt-planner-schedule">
            <header className="hunt-planner-schedule__header">
              <h2 className="hunt-planner-section-title"><CalendarDays className="size-4 text-primary" />{copy.schedule}</h2>
              <div className="flex items-center gap-2 text-xs text-content-muted"><button type="button" className="grid size-7 place-items-center rounded border border-line" aria-label="Previous day"><ChevronLeft className="size-3.5" /></button><strong className="text-info">{copy.today}</strong><button type="button" className="grid size-7 place-items-center rounded border border-line" aria-label="Next day"><ChevronRight className="size-3.5" /></button></div>
            </header>
            <div className="hunt-planner-schedule__track">
              <ScheduleSlot label={selected?.zone_name || sortedRecommendations[0]?.zone_name || copy.find} detail={`${durationHours}h`} primary />
              <ScheduleSlot label={copy.break} detail="1h" />
              <ScheduleSlot label={sortedRecommendations.find((item) => item.zone_id !== selected?.zone_id)?.zone_name || copy.recommended} detail={`${Math.max(1, Math.min(2, durationHours))}h`} />
              <ScheduleSlot label={`+ ${copy.recommended}`} detail={budget ? `${compactNumber(budget)} gp ${copy.session}` : copy.session} />
            </div>
          </section>
        </main>

        <aside className="hunt-planner-preview" aria-label={t('plannerRecovery.inspector')}>
          {selectedIdentifier ? (
            <HuntZonePreviewPanel identifier={selectedIdentifier} />
          ) : (
            <div className="hunt-planner-preview__empty">
              <div>
                <BrandCategoryFallbackIcon category="zones" className="mx-auto size-14 text-primary" />
                <p className="mt-3 text-sm">{copy.preview}</p>
              </div>
            </div>
          )}
        </aside>
      </div>
    </Page>
  );
}

function Metric({
  value,
  max,
  profit = false,
  match = false,
  suffix = '',
}: {
  value?: number | null;
  max: number;
  profit?: boolean;
  match?: boolean;
  suffix?: string;
}) {
  const normalized = value || 0;
  const percent = Math.max(0, Math.min(100, (normalized / Math.max(1, max)) * 100));
  return (
    <span className={`hunt-planner-metric ${profit ? 'hunt-planner-metric--profit' : ''} ${match ? 'hunt-planner-metric--match' : ''}`}>
      <span>{match ? `${Math.round(normalized)}${suffix}` : compactNumber(normalized)}</span>
      <span className="hunt-planner-metric__bar" aria-hidden="true"><span style={{ width: `${percent}%` }} /></span>
    </span>
  );
}

function ScheduleSlot({ label, detail, primary = false }: { label: string; detail: string; primary?: boolean }) {
  return (
    <div className="hunt-planner-schedule__slot" data-primary={primary}>
      <strong>{label}</strong>
      <span>{detail}</span>
    </div>
  );
}
