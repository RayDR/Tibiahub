import { ClipboardList } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  Badge,
  Card,
  DataRegion,
  DegradedState,
  ErrorState,
  LoadingState,
  PaginationControls,
  Table,
  TableContainer,
} from '../../components/ui';
import { WorkspaceContentHeader } from '../../components/workspace/WorkspacePrimitives';
import { AdminGuildWorkspace as Workspace, WorkspaceAuditEntry, workspaceApi } from '../../services/workspaces';
import { formatDateTime } from '../../utils/locale';

const AUDIT_PAGE_SIZE = 20;

export default function AdminGuildWorkspace() {
  const { t, i18n } = useTranslation();
  const { guildKey = '' } = useParams();
  const [data, setData] = useState<Workspace | null>(null);
  const [audits, setAudits] = useState<WorkspaceAuditEntry[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditSkip, setAuditSkip] = useState(0);
  const [loadingAudits, setLoadingAudits] = useState(true);
  const [workspaceError, setWorkspaceError] = useState(false);
  const [auditError, setAuditError] = useState(false);
  const auditRequestRef = useRef<AbortController | null>(null);
  const auditRetrySkipRef = useRef(0);

  const loadWorkspace = useCallback(async () => {
    setWorkspaceError(false);
    try {
      setData(await workspaceApi.adminGuild(guildKey));
    } catch {
      setWorkspaceError(true);
    }
  }, [guildKey]);

  const loadAudits = useCallback(async (nextSkip = 0) => {
    auditRequestRef.current?.abort();
    auditRetrySkipRef.current = nextSkip;
    const controller = new AbortController();
    auditRequestRef.current = controller;
    setLoadingAudits(true);
    setAuditError(false);
    try {
      const page = await workspaceApi.guildAudits(guildKey, nextSkip, AUDIT_PAGE_SIZE, controller.signal);
      if (controller.signal.aborted) return;
      setAudits(page.items);
      setAuditTotal(page.total);
      setAuditSkip(page.skip);
    } catch (loadError: any) {
      if (loadError?.name !== 'CanceledError' && loadError?.code !== 'ERR_CANCELED') setAuditError(true);
    } finally {
      if (auditRequestRef.current === controller) {
        auditRequestRef.current = null;
        setLoadingAudits(false);
      }
    }
  }, [guildKey]);

  useEffect(() => {
    setData(null);
    setAudits([]);
    setAuditTotal(0);
    setAuditSkip(0);
    void loadWorkspace();
    void loadAudits(0);
    return () => auditRequestRef.current?.abort();
  }, [loadAudits, loadWorkspace]);

  if (workspaceError && !data) {
    return <ErrorState title={t('workspace.errors.assistance')} description={t('workspace.errors.tryAgain')} action={<button type="button" onClick={() => void loadWorkspace()} className="app-button-secondary">{t('common.retry')}</button>} />;
  }
  if (!data) return <LoadingState title={t('workspace.common.loading')} />;

  const guild = data.guild;
  const cards = [['members', guild.member_count], ['leader', guild.leader || '—'], ['setup', t(`workspace.setup.${guild.setup_status}`)], ['alerts', guild.open_alerts]];
  return <div className="workspace-page">
    <WorkspaceContentHeader title={guild.name} description={guild.world_name || t('workspace.common.unknownServer')} eyebrow={t('workspace.assistance.badge')} />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(([key, value]) => <Card key={String(key)} className="p-4"><p className="text-xs uppercase text-content-muted">{t(`workspace.common.${key}`)}</p><strong className="mt-1 block text-xl">{value}</strong></Card>)}</div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Link to="/admin/users" className="app-button-primary">{t('workspace.adminNav.users')}</Link>
      <Link to={`/admin/guilds/${guild.key}/raffles`} className="app-button-secondary">{t('raffle.workspace.manageRaffles')}</Link>
      <Link to={`/admin/guilds/${guild.key}/leadership`} className="app-button-secondary">{t('leadership.navigation')}</Link>
      <Link to="/guild" className="app-button-secondary">{t('workspace.assistance.publicView')}</Link>
    </div>
    <section id="audit" className="scroll-mt-28 space-y-3 rounded-xl border border-line p-4">
      <div className="flex items-center gap-2"><ClipboardList className="size-5 text-primary" /><h2 className="font-semibold">{t('workspace.audits.recent')}</h2></div>
      {loadingAudits && audits.length === 0 ? <LoadingState title={t('workspace.common.loading')} /> : auditError && audits.length === 0 ? (
        <DegradedState title={t('workspace.errors.assistance')} description={t('workspace.errors.tryAgain')} action={<button type="button" onClick={() => void loadAudits(auditRetrySkipRef.current)} className="app-button-secondary app-button-sm">{t('common.retry')}</button>} />
      ) : audits.length === 0 ? <p className="text-sm text-content-muted">{t('workspace.audits.noEntries')}</p> : <>
        {auditError ? <DegradedState title={t('workspace.errors.assistance')} description={t('workspace.errors.tryAgain')} action={<button type="button" onClick={() => void loadAudits(auditRetrySkipRef.current)} className="app-button-secondary app-button-sm">{t('common.retry')}</button>} /> : null}
        <div className="responsive-card-list">{audits.map(row => <AuditCard key={row.id} row={row} />)}</div>
        <DataRegion className="responsive-data-table" aria-label={t('workspace.audits.recent')} aria-busy={loadingAudits}>
          <TableContainer><Table><thead><tr><th>{t('workspace.audits.action')}</th><th>{t('workspace.audits.target')}</th><th>{t('workspace.audits.date')}</th></tr></thead><tbody>{audits.map(row => <tr key={row.id}><td><strong>{row.action}</strong></td><td>{row.target_type || '—'}</td><td><Badge>{formatDateTime(row.created_at, i18n.resolvedLanguage || i18n.language)}</Badge></td></tr>)}</tbody></Table></TableContainer>
        </DataRegion>
        <PaginationControls skip={auditSkip} limit={AUDIT_PAGE_SIZE} total={auditTotal} loading={loadingAudits} onPrevious={() => void loadAudits(Math.max(0, auditSkip - AUDIT_PAGE_SIZE))} onNext={() => void loadAudits(auditSkip + AUDIT_PAGE_SIZE)} />
      </>}
    </section>
  </div>;
}

function AuditCard({ row }: { row: WorkspaceAuditEntry }) {
  const { i18n } = useTranslation();
  return <article className="rounded-lg bg-surface-raised p-3 text-sm"><strong>{row.action}</strong>{row.target_type ? <p className="text-xs text-content-muted">{row.target_type}</p> : null}<Badge className="mt-2">{formatDateTime(row.created_at, i18n.resolvedLanguage || i18n.language)}</Badge></article>;
}
