import { Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import '../../i18n/questEnhancements';
import type { QuestProgressStatus } from '../../services/questProgress';

export default function QuestProgressMeter({
  completed,
  total,
  status,
  compact = false,
}: {
  completed: number;
  total: number;
  status: QuestProgressStatus;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const safeTotal = Math.max(0, total);
  const safeCompleted = Math.min(Math.max(0, completed), safeTotal || completed);
  const statusLabel = status === 'completed'
    ? t('questEnhancement.completed')
    : status === 'in_progress'
      ? t('questEnhancement.inProgress')
      : t('questEnhancement.notStarted');

  return (
    <div className={compact ? 'space-y-1.5' : 'space-y-2'} aria-label={`${statusLabel}${safeTotal ? `, ${safeCompleted}/${safeTotal}` : ''}`}>
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className={`inline-flex items-center gap-1.5 font-semibold ${status === 'completed' ? 'text-success' : status === 'in_progress' ? 'text-primary' : 'text-content-muted'}`}>
          {status === 'completed' ? <Check className="size-3.5" /> : null}
          {statusLabel}
        </span>
        {safeTotal > 0 ? (
          <span className="tabular-nums text-content-muted">
            {t('questEnhancement.completedSteps', { completed: safeCompleted, total: safeTotal })}
          </span>
        ) : null}
      </div>

      {safeTotal > 0 ? (
        <div
          className={`grid overflow-hidden rounded-full border border-line bg-surface-base ${compact ? 'h-2' : 'h-2.5'}`}
          style={{ gridTemplateColumns: `repeat(${safeTotal}, minmax(0, 1fr))` }}
          aria-hidden="true"
        >
          {Array.from({ length: safeTotal }, (_, index) => (
            <span
              key={index}
              className={`border-r border-surface-overlay last:border-r-0 ${index < safeCompleted ? 'bg-success' : 'bg-surface-raised'}`}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
