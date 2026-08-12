import { ExternalLink, MessageSquarePlus } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const ISSUE_BASE = 'https://github.com/RayDR/Tibiahub/issues/new';

export function buildIssueUrl({ template, title, context }: { template: string; title: string; context?: string }) {
  const params = new URLSearchParams({ template, title });
  if (context) params.set('body', context);
  return `${ISSUE_BASE}?${params.toString()}`;
}

export function SuggestImprovementLink({ className = '' }: { className?: string }) {
  const { t } = useTranslation();
  return <a href={buildIssueUrl({ template: 'feature-request.yml', title: '[Suggestion] ' })} target="_blank" rel="noreferrer" className={`inline-flex min-h-11 items-center gap-2 text-sm text-primary hover:underline ${className}`}><MessageSquarePlus size={16} />{t('feedback.improvement')}<ExternalLink size={13} /></a>;
}

export function SuggestCorrectionLink({ entityType, entityName, className = '' }: { entityType: string; entityName: string; className?: string }) {
  const { t } = useTranslation();
  const pageUrl = typeof window === 'undefined' ? '' : window.location.href;
  const context = `### TibiaHub context\n\n- Entity type: ${entityType}\n- Entity name: ${entityName}\n- Page: ${pageUrl}\n\nPlease describe the correction below. Nothing is sent until you submit this GitHub issue.\n`;
  return <a href={buildIssueUrl({ template: 'knowledge-data-correction.yml', title: `[Knowledge correction] ${entityName}`, context })} target="_blank" rel="noreferrer" className={`inline-flex min-h-11 items-center gap-2 rounded-lg border border-line px-3 text-sm text-content-secondary hover:border-primary hover:text-primary ${className}`}><MessageSquarePlus size={16} />{t('feedback.correction')}<ExternalLink size={13} /></a>;
}
