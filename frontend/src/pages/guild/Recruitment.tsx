import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { EmptyState, WorkspaceHeader } from '../../components/workspace/WorkspacePrimitives';

export default function Recruitment() { const { t } = useTranslation(); return <div className="space-y-4"><WorkspaceHeader title={t('workspace.recruitment.title')} subtitle={t('workspace.recruitment.subtitle')} /><EmptyState title={t('workspace.recruitment.empty')} description={t('workspace.recruitment.help')} action={<Link to="/guild/members" className="inline-flex min-h-11 items-center rounded-lg bg-amber-500 px-4 py-2 font-semibold text-slate-950">{t('workspace.recruitment.members')}</Link>} /></div>; }
