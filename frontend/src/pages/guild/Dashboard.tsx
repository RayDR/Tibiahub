import { Badge as RankIcon, CalendarClock, Compass, Megaphone, Shield, Sword, UserPlus, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Badge, Card, Dialog, EmptyState, LoadingState, PageHeader, Panel } from '../../components/ui';
import { useAuth } from '../../context/AuthContext';
import { Announcement, guildApi } from '../../services/guild';
import { LeadershipSummary, leadershipApi } from '../../services/leadership';
import { useGuildContext } from '../../utils/guildContext';

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const guildName = useGuildContext(user);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [detail, setDetail] = useState<Announcement | null>(null);
  const [leadership, setLeadership] = useState<LeadershipSummary | null>(null);

  const load = async () => {
    if (!guildName) return;
    setLoading(true); setError(false);
    const [announcementResult, leadershipResult] = await Promise.allSettled([guildApi.getAnnouncements(0, 3, guildName), leadershipApi.summary()]);
    if (announcementResult.status === 'fulfilled') setAnnouncements(announcementResult.value); else setError(true);
    if (leadershipResult.status === 'fulfilled') setLeadership(leadershipResult.value); else setLeadership(null);
    setLoading(false);
  };
  useEffect(() => { void load(); }, [guildName]);

  if (loading) return <LoadingState title={t('guildDashboard.loading')} />;
  return <div className="space-y-5">
    <PageHeader size="md" eyebrow={t('guildDashboard.eyebrow')} title={t('guildDashboard.title')} subtitle={t('guildDashboard.subtitle')} primaryAction={<Link to="/guild/events" className="app-button-primary"><CalendarClock className="size-4" />{t('guildDashboard.actions.events')}</Link>} secondaryActions={<Link to="/guild/members" className="app-button-secondary"><Users className="size-4" />{t('guildDashboard.actions.members')}</Link>} />
    {error ? <div className="rounded-xl border border-warning/40 bg-warning-subtle p-3 text-sm text-warning">{t('guildDashboard.partialError')}</div> : null}

    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label={t('guildDashboard.characterSummary')}>
      <Summary icon={<Shield />} label={t('guildDashboard.fields.role')} value={user?.guild_rank || t('guildDashboard.values.unranked')} />
      <Summary icon={<RankIcon />} label={t('guildDashboard.fields.level')} value={user?.level ?? t('common.notAvailable')} />
      <Summary icon={<Sword />} label={t('guildDashboard.fields.vocation')} value={user?.vocation || t('common.unknown')} />
      <Summary icon={<Compass />} label={t('guildDashboard.fields.world')} value={user?.world_name || t('common.unknown')} />
    </section>

    {leadership ? <Link to="/guild/leadership"><Panel className="flex flex-col gap-3 border-primary/30 bg-primary-subtle p-4 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex items-center gap-2"><UserPlus className="size-5 text-primary" /><h2 className="font-semibold">{t('leadership.title')}</h2></div><p className="mt-1 text-sm text-content-secondary">{t('guildDashboard.leadershipSummary', { active: leadership.active_viceleaders, openings: leadership.open_positions })}</p></div>{leadership.below_recommended ? <Badge tone="warning">{t('leadership.dashboard.attention')}</Badge> : <Badge tone="success">{t('workspace.setup.ready')}</Badge>}</Panel></Link> : null}

    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(16rem,.7fr)]">
      <section className="rounded-xl border border-line p-4"><div className="mb-4 flex items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><Megaphone className="size-5 text-primary" />{t('guild.latestAnnouncements')}</h2><p className="text-sm text-content-muted">{t('guildDashboard.announcementsHelp')}</p></div><Link to="/guild/announcements" className="app-button-ghost app-button-sm">{t('guild.viewAll')}</Link></div>{announcements.length ? <div className="grid gap-3">{announcements.map(item => <button type="button" key={item.id} onClick={() => setDetail(item)} className="rounded-lg border border-line bg-surface-raised p-3 text-left hover:border-primary/50"><div className="flex items-start justify-between gap-2"><strong>{item.title}</strong><Badge>{item.type}</Badge></div><p className="mt-1 line-clamp-2 text-sm text-content-secondary">{item.content}</p><p className="mt-2 text-xs text-content-muted">{t('guildDashboard.published', { author: item.author?.username || t('common.unknown'), date: new Date(item.created_at).toLocaleString(i18n.language) })}</p></button>)}</div> : <EmptyState title={t('guild.noAnnouncements')} description={t('guildDashboard.noAnnouncementsHelp')} />}</section>
      <section className="rounded-xl border border-line p-4"><h2 className="font-semibold">{t('guildDashboard.quickActions.title')}</h2><p className="mt-1 text-sm text-content-muted">{t('guildDashboard.quickActions.help')}</p><div className="mt-4 grid gap-2">{[
        ['/guild/hunts', Compass, 'hunts'], ['/guild/leadership', UserPlus, 'leadership'], ['/guild/notifications', Megaphone, 'notifications'],
      ].map(([to, Icon, key]) => <Link key={String(to)} to={String(to)} className="workspace-nav-link w-full"><Icon className="size-4" />{t(`guildDashboard.quickActions.${key}`)}</Link>)}</div></section>
    </div>

    <Dialog open={Boolean(detail)} onClose={() => setDetail(null)} label={detail?.title || t('guildDashboard.announcementDetail')} className="p-5 sm:p-6">{detail ? <><div className="flex items-start justify-between gap-3"><div><Badge>{detail.type}</Badge><h2 className="mt-2 text-xl font-semibold">{detail.title}</h2></div><button type="button" onClick={() => setDetail(null)} className="app-button-ghost app-button-sm" aria-label={t('common.close')}>×</button></div><p className="mt-4 whitespace-pre-line text-content-secondary">{detail.content}</p><p className="mt-4 text-xs text-content-muted">{new Date(detail.created_at).toLocaleString(i18n.language)}</p></> : null}</Dialog>
  </div>;
}

function Summary({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) { return <Card className="flex items-center gap-3 p-4"><span className="grid size-9 place-items-center rounded-lg bg-primary-subtle text-primary">{icon}</span><div className="min-w-0"><p className="text-xs uppercase tracking-wide text-content-muted">{label}</p><p className="truncate font-semibold">{value}</p></div></Card>; }
