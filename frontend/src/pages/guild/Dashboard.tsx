import { useEffect, useState } from 'react';
import { guildApi, Announcement } from '../../services/guild';
import { Megaphone, CalendarClock, Loader2, User } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';
import { Sword, Shield, Badge } from 'lucide-react';
import { useGuildContext } from '../../utils/guildContext';
import { LeadershipSummary, leadershipApi } from '../../services/leadership';

export default function Dashboard() {
    const { t } = useTranslation();
    const { user } = useAuth();
    const guildName = useGuildContext(user);
    const [announcements, setAnnouncements] = useState<Announcement[]>([]);
    const [loading, setLoading] = useState(true);
    const [detailModal, setDetailModal] = useState<Announcement | null>(null);
    const [leadership, setLeadership] = useState<LeadershipSummary | null>(null);

    useEffect(() => {
        const loadData = async () => {
            try {
                if (!guildName) {
                    setAnnouncements([]);
                    return;
                }
                const data = await guildApi.getAnnouncements(0, 3, guildName);
                setAnnouncements(data);
            } catch (error) {
                console.error("Failed to load dashboard data", error);
            } finally {
                setLoading(false);
            }
        };
        void loadData();
    }, [guildName]);

    useEffect(() => { if (guildName) void leadershipApi.summary().then(setLeadership).catch(() => setLeadership(null)); }, [guildName]);

    return (
        <div className="space-y-6 sm:space-y-8">
            {/* Guild Header with Images */}
            <div className="relative bg-gradient-to-r from-surface-base to-surface border border-line rounded-lg overflow-hidden">
                <div className="absolute inset-0 opacity-10">
                    <img src="/assets/guild/bw_fire.png" alt="" className="w-full h-full object-cover" />
                </div>
                <div className="relative p-4 sm:p-8 flex flex-col sm:flex-row items-center gap-4 sm:gap-6">
                    <img src="/assets/guild/bw-ash.png" alt="Ashclaw Guild" className="w-20 h-20 sm:w-24 sm:h-24 rounded-lg border-2 border-primary shadow-lg" />
                    <div className="text-center sm:text-left">
                        <h1 className="text-3xl sm:text-4xl font-serif text-content-primary mb-2">Bloodborne Warhowl</h1>
                        <p className="text-content-secondary">{t('guild.welcomeMessage')}</p>
                        <div className="mt-2 text-sm text-primary">
                            {t('guild.guildLeader')}: Ray On

                                                {/* User Info */}
                                                {user && (
                                                    <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4 border-t border-line">
                                                        <div className="text-xs">
                                                            <p className="text-content-muted flex items-center gap-1"><Shield className="w-3 h-3" /> Rango</p>
                                                            <p className="text-primary font-semibold">{user.guild_rank || 'Unranked'}</p>
                                                        </div>
                                                        {user.level && (
                                                            <div className="text-xs">
                                                                <p className="text-content-muted flex items-center gap-1"><Badge className="w-3 h-3" /> Nivel</p>
                                                                <p className="text-primary font-semibold">{user.level}</p>
                                                            </div>
                                                        )}
                                                        {user.vocation && (
                                                            <div className="text-xs">
                                                                <p className="text-content-muted flex items-center gap-1"><Sword className="w-3 h-3" /> Clase</p>
                                                                <p className="text-primary font-semibold">{user.vocation}</p>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                        </div>
                    </div>
                </div>
            </div>

            {leadership && <Link to="/guild/leadership" className="block rounded-xl border border-primary/30 bg-primary/10 p-4">
                <div className="flex items-center justify-between gap-3"><div><h2 className="font-semibold text-primary">{t('leadership.title')}</h2><p className="mt-1 text-sm text-content-secondary">{t('leadership.summary.active')}: {leadership.active_viceleaders} · {t('leadership.summary.positions')}: {leadership.open_positions}{leadership.capabilities.review && leadership.active_applicants !== undefined ? ` · ${t('leadership.summary.applicants')}: ${leadership.active_applicants}` : ''}{!leadership.capabilities.review && leadership.own_status ? ` · ${t(`leadership.status.${leadership.own_status}`)}` : ''}</p></div>{leadership.below_recommended && <span className="rounded-full bg-primary/20 px-3 py-1 text-xs text-primary">{t('leadership.warning.title')}</span>}</div>
            </Link>}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
                {/* Latest Announcements */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-4 sm:p-5">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold text-primary flex items-center gap-2 text-sm sm:text-base">
                            <Megaphone className="w-4 h-4" />
                            {t('guild.latestAnnouncements')}
                        </h3>
                        <Link to="/guild/announcements" className="text-xs text-content-secondary hover:text-content-primary">{t('guild.viewAll')}</Link>
                    </div>

                    <div className="space-y-4">
                        {loading ? (
                            <div className="flex justify-center p-4">
                                <Loader2 className="w-6 h-6 animate-spin text-primary" />
                            </div>
                        ) : announcements.length > 0 ? (
                            announcements.map((ann) => (
                                <div
                                    key={ann.id}
                                    onClick={() => setDetailModal(ann)}
                                    className="p-3 bg-surface-base/50 rounded border border-line hover:border-primary/50 transition-colors cursor-pointer"
                                >
                                    <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ml-auto float-right ${ann.type === 'contest' ? 'bg-accent/50 text-accent' :
                                        ann.type === 'hunt' ? 'bg-danger/50 text-danger' :
                                            'bg-surface text-content-secondary'
                                        }`}>
                                        {ann.type}
                                    </span>
                                    <h4 className="font-medium text-content-primary">{ann.title}</h4>
                                    <p className="text-xs text-content-muted mt-1 truncate">{ann.content}</p>
                                    <div className="text-xs text-content-muted mt-1">
                                        {t('guild.by')} {ann.author?.is_superuser ? 'Ray On' : ann.author?.username}
                                    </div>
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-content-muted italic">{t('guild.noAnnouncements')}</p>
                        )}
                    </div>
                </div>

                {/* Upcoming Events (Placeholder for now) */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-4 sm:p-5 opacity-70">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold text-primary flex items-center gap-2 text-sm sm:text-base">
                            <CalendarClock className="w-4 h-4" />
                            {t('guild.upcomingActivities')}
                        </h3>
                        <Link to="/guild/events" className="text-xs text-content-secondary hover:text-content-primary">{t('guild.viewAll')}</Link>
                    </div>
                    <p className="text-sm text-content-muted italic">{t('guild.noUpcoming')}</p>
                </div>
            </div>

            {/* Announcement Detail Modal */}
            {detailModal && (
                <div
                    className="fixed inset-0 bg-surface-base/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                    onClick={() => setDetailModal(null)}
                >
                    <div
                        className="bg-surface-base border border-line rounded-lg w-full max-w-3xl shadow-2xl max-h-[80vh] overflow-y-auto"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="sticky top-0 bg-surface-base p-6 border-b border-line flex items-center justify-between">
                            <div className="flex-1">
                                <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider mb-2 ${
                                    detailModal.type === 'contest' ? 'bg-accent/50 text-accent ring-1 ring-accent/50' :
                                    detailModal.type === 'hunt' ? 'bg-danger/50 text-danger ring-1 ring-danger/50' :
                                    'bg-surface text-content-secondary ring-1 ring-line-focus'
                                }`}>
                                    {detailModal.type}
                                </span>
                                <h3 className="text-2xl font-bold text-content-primary">{detailModal.title}</h3>
                                <div className="flex items-center gap-4 mt-2 text-sm text-content-secondary">
                                    <div className="flex items-center gap-1">
                                        <User className="w-4 h-4" />
                                        {detailModal.author?.is_superuser ? 'Ray On' : detailModal.author?.username}
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <CalendarClock className="w-4 h-4" />
                                        {new Date(detailModal.created_at).toLocaleString()}
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={() => setDetailModal(null)}
                                className="text-content-secondary hover:text-content-primary p-2 text-xl"
                            >
                                ×
                            </button>
                        </div>

                        <div className="p-6">
                            <div className="prose prose-invert prose-sm max-w-none text-content-secondary whitespace-pre-line">
                                {detailModal.content}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
