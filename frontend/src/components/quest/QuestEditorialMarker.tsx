import { useTranslation } from 'react-i18next';

export interface QuestEditorialPresentation {
  state: 'approved' | 'published';
  version: number;
  author?: string;
  reviewer?: string;
  publishedAt?: string;
}

export default function QuestEditorialMarker({ editorial }: { editorial?: QuestEditorialPresentation | null }) {
  const { t } = useTranslation();
  if (!editorial) return null;
  return (
    <span className="inline-flex items-center rounded-full border border-success/35 bg-success/10 px-2.5 py-1 text-xs font-semibold text-success">
      {t(`questDetail.editorial.${editorial.state}`)} · {t('questDetail.editorial.version', { version: editorial.version })}
    </span>
  );
}
