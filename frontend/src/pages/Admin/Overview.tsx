import { Activity, AlertTriangle, Bug, Database, Globe, RefreshCw, ScrollText, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Card, EmptyState, LoadingState, PageHeader, Panel } from '../../components/ui';
import { adminOverviewApi, systemApi } from '../../services/api';
import { guildManagementApi } from '../../services/guildManagement';

interface Stats { creatures: { total: number; visible: number; hidden: number }; hunt_zones: { total: number }; quests: { total: number }; users: { total: number; active: number; inactive: number; admin: number } }
interface TibiaStatus { status: 'online' | 'offline' | 'degraded'; latency_ms?: number | null; message: string; last_check: string }

export default function Overview() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<Stats | null>(null);
  const [tibiaStatus, setTibiaStatus] = useState<TibiaStatus | null>(null);
  const [dataVersion, setDataVersion] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [partialError, setPartialError] = useState(false);
  const load = async (refresh = false) => {
    refresh ? setRefreshing(true) : setLoading(true); setPartialError(false);
    const results = await Promise.allSettled([adminOverviewApi.getStats(), guildManagementApi.getTibiaAPIStatus(), systemApi.getHealth()]);
    if (results[0].status === 'fulfilled') setStats(results[0].value);
    if (results[1].status === 'fulfilled') setTibiaStatus(results[1].value);
    if (results[2].status === 'fulfilled') setDataVersion(results[2].value.external_sync?.latest_data_version ?? null);
    setPartialError(results.some(result => result.status === 'rejected')); setLoading(false); setRefreshing(false);
  };
  useEffect(() => { void load(); }, []);
  if (loading) return <LoadingState title={t('adminOverview.loading')} />;
  if (!stats && !tibiaStatus && !dataVersion) return <EmptyState title={t('adminOverview.error')} description={t('adminOverview.errorHelp')} action={<AppButton onClick={() => void load()}>{t('common.retry')}</AppButton>} />;
  const attention = tibiaStatus?.status !== 'online' || (stats?.creatures.hidden || 0) > 0;

  return <div className="space-y-6">
    <PageHeader size="md" title={t('adminOverview.title')} subtitle={t('adminOverview.subtitle')} iconElement={<Activity className="size-6" />} primaryAction={<AppButton onClick={() => void load(true)} disabled={refreshing}>{<RefreshCw className={`size-4 ${refreshing ? 'animate-spin' : ''}`} />}{t('common.refresh')}</AppButton>} />
    {partialError ? <div className="rounded-xl border border-warning/40 bg-warning-subtle p-3 text-sm text-warning">{t('adminOverview.partialError')}</div> : null}
    <div className="grid gap-4 md:grid-cols-3">
      <Panel className="p-4"><div className="flex items-center justify-between"><span className="flex items-center gap-2 text-sm text-content-secondary"><Globe className="size-4" />{t('adminOverview.status.api')}</span><Badge tone={tibiaStatus?.status === 'online' ? 'success' : tibiaStatus?.status === 'offline' ? 'danger' : 'warning'}>{tibiaStatus ? t(`adminOverview.values.${tibiaStatus.status}`) : t('common.notAvailable')}</Badge></div><p className="mt-3 text-2xl font-bold">{tibiaStatus?.latency_ms != null ? t('adminOverview.status.latency', { value: Number(tibiaStatus.latency_ms).toFixed(0) }) : t('common.notAvailable')}</p><p className="mt-1 text-xs text-content-muted">{tibiaStatus?.message || t('adminOverview.status.noMessage')}</p></Panel>
      <Panel className="p-4"><span className="flex items-center gap-2 text-sm text-content-secondary"><Database className="size-4" />{t('adminOverview.status.dataVersion')}</span><p className="mt-3 truncate text-xl font-bold">{dataVersion || t('common.notAvailable')}</p><p className="mt-1 text-xs text-content-muted">{t('adminOverview.status.dataVersionHelp')}</p></Panel>
      <Link to={attention ? '/admin/assistance' : '/admin/audits'}><Panel className={`h-full p-4 ${attention ? 'border-warning/40 bg-warning-subtle' : 'border-success/40 bg-success-subtle'}`}><span className="flex items-center gap-2 text-sm"><AlertTriangle className={`size-4 ${attention ? 'text-warning' : 'text-success'}`} />{t('adminOverview.attention.title')}</span><p className="mt-3 text-xl font-bold">{t(attention ? 'adminOverview.attention.required' : 'adminOverview.attention.clear')}</p><p className="mt-1 text-xs text-content-muted">{t('adminOverview.attention.help')}</p></Panel></Link>
    </div>
    <MetricSection icon={<Bug />} title={t('adminOverview.sections.cyclopedia')}><Stat label={t('adminOverview.metrics.totalCreatures')} value={stats?.creatures.total} /><Stat label={t('adminOverview.metrics.visible')} value={stats?.creatures.visible} tone="success" /><Stat label={t('adminOverview.metrics.hidden')} value={stats?.creatures.hidden} tone="danger" /></MetricSection>
    <MetricSection icon={<ScrollText />} title={t('adminOverview.sections.content')}><Stat label={t('adminOverview.metrics.quests')} value={stats?.quests.total} /><Stat label={t('adminOverview.metrics.zones')} value={stats?.hunt_zones.total} /></MetricSection>
    <MetricSection icon={<Users />} title={t('adminOverview.sections.users')}><Stat label={t('adminOverview.metrics.totalUsers')} value={stats?.users.total} /><Stat label={t('adminOverview.metrics.active')} value={stats?.users.active} tone="success" /><Stat label={t('adminOverview.metrics.inactive')} value={stats?.users.inactive} /><Stat label={t('adminOverview.metrics.admins')} value={stats?.users.admin} tone="primary" /></MetricSection>
  </div>;
}

function MetricSection({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) { return <section><h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-content-muted">{icon}{title}</h2><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{children}</div></section>; }
function Stat({ label, value, tone }: { label: string; value?: number; tone?: 'success' | 'danger' | 'primary' }) { const toneClass = tone === 'success' ? 'text-success' : tone === 'danger' ? 'text-danger' : tone === 'primary' ? 'text-primary' : 'text-content-primary'; return <Card className="p-4"><p className="text-xs uppercase tracking-wide text-content-muted">{label}</p><p className={`mt-1 text-3xl font-bold ${toneClass}`}>{value ?? '—'}</p></Card>; }
