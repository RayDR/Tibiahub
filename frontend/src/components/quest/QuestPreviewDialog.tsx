import { BookOpen, Loader2, MapPin, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import type { QuestBrowseResult } from '../../services/questBrowser';
import type { QuestDetail } from '../../types';
import { hasDetailedQuestData, hasDetailedQuestSummary, questDetailCounts } from '../../utils/questPresentation';
import { Dialog } from '../ui/Overlay';

export default function QuestPreviewDialog({
  open,
  quest,
  detail,
  loading,
  error,
  linkState,
  onClose,
  onNavigate,
}: {
  open: boolean;
  quest: QuestBrowseResult | null;
  detail: QuestDetail | null;
  loading: boolean;
  error: boolean;
  linkState?: unknown;
  onClose: () => void;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation();
  if (!quest) return null;
  const counts = questDetailCounts(detail);
  const hasDetails = detail ? hasDetailedQuestData(detail) : hasDetailedQuestSummary(quest);
  const route = `/quests/${quest.slug || quest.id}`;
  const location = detail?.locations[0]?.name || quest.location;

  return <Dialog open={open} onClose={onClose} label={t('questDetail.previewTitle', { name: quest.name })} className="quest-preview-dialog quest-codex w-[min(94vw,46rem)] overflow-hidden p-0">
    <div className="quest-codex__binding" />
    <div className="quest-codex__pages p-5 sm:p-7">
      <button type="button" onClick={onClose} className="absolute right-3 top-3 grid size-11 place-items-center rounded-full text-current hover:bg-primary/10" aria-label={t('common.close')}><X className="size-5" /></button>
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">{t('questDetail.codexEntry')}</p>
      <h2 className="mt-2 pr-10 font-serif text-2xl font-bold sm:text-3xl">{quest.name}</h2>
      <p className="mt-4 text-sm leading-6">{detail?.summary || detail?.description || quest.description || t('questDetail.noDetails')}</p>

      <div className="mt-5 flex flex-wrap gap-2 text-xs">
        <span className="quest-codex__chip rounded-full border px-2.5 py-1">{t('questDetail.minimumLevel')}: {quest.min_level ?? t('questDetail.unknown')}</span>
        {quest.is_access_quest ? <span className="quest-codex__chip rounded-full border px-2.5 py-1">{t('questDetail.access')}</span> : null}
        {quest.premium_required != null ? <span className="quest-codex__chip rounded-full border px-2.5 py-1">{t('questDetail.premium')}: {t(quest.premium_required ? 'questDetail.yes' : 'questDetail.no')}</span> : null}
        {quest.repeatable != null ? <span className="quest-codex__chip rounded-full border px-2.5 py-1">{t('questDetail.repeatable')}: {t(quest.repeatable ? 'questDetail.yes' : 'questDetail.no')}</span> : null}
        {location ? <span className="quest-codex__chip inline-flex items-center gap-1 rounded-full border px-2.5 py-1"><MapPin className="size-3" />{location}</span> : null}
      </div>

      {loading ? <div className="mt-5 flex items-center gap-2 text-sm"><Loader2 className="size-4 animate-spin" />{t('common.loading')}</div> : null}
      {!loading && !error && hasDetails ? <dl className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {Object.entries(counts).map(([key, value]) => <div key={key} className="quest-codex__fact rounded-lg border p-3"><dt className="text-xs">{t(`questDetail.previewCounts.${key}`)}</dt><dd className="mt-1 font-bold">{value}</dd></div>)}
      </dl> : null}
      {!loading && (!hasDetails || error) ? <div className="quest-codex__empty mt-5 rounded-lg border border-dashed p-4 text-sm"><strong>{t('questDetail.noDetailedData')}</strong><p className="mt-1">{t('questDetail.noDetailedDataHelp')}</p></div> : null}

      <div className="mt-6 flex flex-col-reverse gap-2 border-t border-current/15 pt-4 sm:flex-row sm:justify-end">
        <button type="button" onClick={onClose} className="app-button-ghost min-h-11">{t('common.close')}</button>
        <Link to={route} state={linkState} onClick={() => { onClose(); onNavigate?.(); }} className="app-button-primary min-h-11"><BookOpen className="size-4" />{t('questDetail.openQuest')}</Link>
      </div>
    </div>
  </Dialog>;
}
