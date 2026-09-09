import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Crown,
  Gift,
  KeyRound,
  ListOrdered,
  Loader2,
  MapPin,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import ImageWithFallback from '../ImageWithFallback';
import { questsApi } from '../../services/api';
import type { QuestDetail } from '../../types';

function booleanLabel(value: boolean | null | undefined, yes: string, no: string, unknown: string): string {
  if (value == null) return unknown;
  return value ? yes : no;
}

function names(values: Array<{ name: string }>, limit = 4): string[] {
  return values.slice(0, limit).map((value) => value.name);
}

export default function QuestPreviewPanel({ identifier }: { identifier: string }) {
  const { t } = useTranslation();
  const location = useLocation();
  const [quest, setQuest] = useState<QuestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setQuest(null);
    setLoading(true);
    setError(false);
    void questsApi.getById(identifier, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setQuest(result);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [identifier]);

  const route = quest ? `/quests/${quest.slug || quest.id}` : `/quests/${identifier}`;
  const linkState = { from: `${location.pathname}${location.search}` };
  const locationLabel = quest?.locations[0]?.name || quest?.location;
  const npcLabel = quest?.starting_npcs[0]?.name || quest?.related_npcs[0]?.name || quest?.npc;
  const requirementCount = quest
    ? quest.required_items.length + quest.required_quests.length + quest.required_creatures.length
    : 0;
  const rewardCount = quest?.rewarded_items.length || 0;
  const chips = useMemo(() => quest ? [
    quest.category,
    quest.quest_type,
    quest.difficulty,
    quest.group_name,
  ].filter((value): value is string => Boolean(value)) : [], [quest]);

  if (loading) {
    return (
      <section className="quest-preview-panel quest-preview-loading" aria-live="polite">
        <Loader2 className="size-6 animate-spin text-primary" />
        <span>{t('common.loading')}</span>
      </section>
    );
  }

  if (error || !quest) {
    return (
      <section className="quest-preview-panel p-5">
        <h2 className="font-serif text-lg font-semibold text-content-primary">{t('questDetail.unavailable')}</h2>
        <p className="mt-2 text-sm text-content-muted">{t('questDetail.notFound')}</p>
      </section>
    );
  }

  return (
    <section className="quest-preview-panel">
      <header className="quest-preview-identity">
        <div className="quest-preview-art">
          <ImageWithFallback
            src={quest.image_url}
            alt={quest.name}
            fallbackKind="quest"
            fallbackLabel={quest.name}
            className="size-full object-contain [image-rendering:pixelated]"
            containerClassName="size-full"
          />
        </div>
        <div className="min-w-0">
          <p className="text-[0.68rem] font-bold uppercase tracking-[0.2em] text-primary">{t('questDetail.codexEntry')}</p>
          <h2 className="quest-preview-name">{quest.name}</h2>
          {chips.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {chips.slice(0, 4).map((chip) => <span key={chip} className="quest-preview-chip">{chip}</span>)}
            </div>
          ) : null}
          <p className="mt-3 line-clamp-4 text-sm leading-6 text-content-secondary">
            {quest.summary || quest.description || t('questDetail.noDetails')}
          </p>
        </div>
      </header>

      <div className="quest-preview-stats">
        <PreviewStat label={t('questDetail.minimumLevel')} value={quest.min_level?.toLocaleString() || '—'} />
        <PreviewStat label={t('questDetail.experience')} value={quest.experience_reward?.toLocaleString() || '—'} />
        <PreviewStat label={t('questDetail.missions', { count: quest.missions.length })} value={quest.missions.length.toLocaleString()} />
      </div>

      <div className="quest-preview-flags">
        <span><Crown className="size-4 text-primary" />{t('questDetail.premium')}: {booleanLabel(quest.premium_required, t('questDetail.yes'), t('questDetail.no'), t('questDetail.unknown'))}</span>
        <span><BookOpen className="size-4 text-primary" />{t('questDetail.repeatable')}: {booleanLabel(quest.repeatable, t('questDetail.yes'), t('questDetail.no'), t('questDetail.unknown'))}</span>
        {quest.solo_possible != null ? <span><ShieldCheck className="size-4 text-primary" />Solo: {quest.solo_possible ? t('questDetail.yes') : t('questDetail.no')}</span> : null}
        {quest.duration ? <span><ListOrdered className="size-4 text-primary" />{quest.duration}</span> : null}
      </div>

      {(locationLabel || npcLabel) ? (
        <section className="quest-preview-section">
          <h3 className="quest-preview-section-title"><MapPin className="size-4 text-primary" />{t('questDetail.locations')}</h3>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {locationLabel ? <PreviewMeta icon={<MapPin className="size-4" />} label={locationLabel} /> : null}
            {npcLabel ? <PreviewMeta icon={<UserRound className="size-4" />} label={npcLabel} /> : null}
          </div>
        </section>
      ) : null}

      <div className="quest-preview-columns">
        <section>
          <h3 className="quest-preview-section-title"><KeyRound className="size-4 text-primary" />{t('questDetail.requirements', { count: requirementCount })}</h3>
          <div className="quest-preview-list">
            {quest.required_items.slice(0, 3).map((item) => (
              <div key={`item-${item.name}`} className="quest-preview-row">
                <span className="truncate">{item.name}</span>
                {item.amount > 1 ? <strong>×{item.amount}</strong> : null}
              </div>
            ))}
            {quest.required_quests.slice(0, Math.max(0, 3 - quest.required_items.length)).map((required) => (
              <div key={`quest-${required.name}`} className="quest-preview-row"><span className="truncate">{required.name}</span></div>
            ))}
            {requirementCount === 0 ? <p className="py-2 text-xs text-content-muted">{t('questDetail.noRequirements')}</p> : null}
          </div>
        </section>

        <section>
          <h3 className="quest-preview-section-title"><Gift className="size-4 text-primary" />{t('questDetail.rewards', { count: rewardCount })}</h3>
          <div className="quest-preview-list">
            {quest.rewarded_items.slice(0, 4).map((item) => (
              <div key={item.name} className="quest-preview-row">
                <span className="truncate">{item.name}</span>
                {item.amount > 1 ? <strong>×{item.amount}</strong> : null}
              </div>
            ))}
            {rewardCount === 0 ? <p className="py-2 text-xs text-content-muted">{t('questDetail.noRewards')}</p> : null}
          </div>
        </section>
      </div>

      {quest.missions.length ? (
        <section className="quest-preview-section">
          <h3 className="quest-preview-section-title"><ListOrdered className="size-4 text-primary" />{t('questEnhancement.missionIndex')} ({quest.missions.length})</h3>
          <ol className="quest-preview-missions">
            {quest.missions.slice(0, 5).map((mission) => (
              <li key={mission.id}>
                <Link to={`${route}#mission-${mission.id}`} state={linkState} className="quest-preview-mission-link">
                  <span>{mission.sequence}</span>
                  <strong className="truncate">{mission.title}</strong>
                  <ArrowRight className="size-3.5 shrink-0" />
                </Link>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {(quest.access_unlocks.length || quest.bosses.length || quest.related_creatures.length) ? (
        <section className="quest-preview-section">
          <h3 className="quest-preview-section-title"><ShieldCheck className="size-4 text-primary" />{t('questDetail.access')}</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {quest.access_unlocks.slice(0, 3).map((unlock) => <span key={unlock.name} className="quest-preview-chip">{unlock.name}</span>)}
            {names(quest.bosses, 2).map((boss) => <span key={`boss-${boss}`} className="quest-preview-chip">{boss}</span>)}
            {quest.related_creatures.slice(0, 2).map((creature) => <span key={`creature-${creature.creature_name}`} className="quest-preview-chip">{creature.creature_name}</span>)}
          </div>
        </section>
      ) : null}

      <Link to={route} state={linkState} className="quest-preview-full-link">
        <BookOpen className="size-4" />
        {t('questDetail.openQuest')}
        <ArrowRight className="size-4" />
      </Link>
    </section>
  );
}

function PreviewStat({ label, value }: { label: string; value: string }) {
  return <div className="quest-preview-stat"><span>{label}</span><strong>{value}</strong></div>;
}

function PreviewMeta({ icon, label }: { icon: React.ReactNode; label: string }) {
  return <div className="quest-preview-meta"><span className="text-primary">{icon}</span><span className="truncate">{label}</span></div>;
}
