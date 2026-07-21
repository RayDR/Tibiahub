import { useEffect, useState, useRef, useCallback } from 'react';
import { guildApi, Announcement } from '../../services/guild';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useTranslation } from 'react-i18next';

import { Plus, Megaphone, Loader2, Filter, X, CalendarClock, User } from 'lucide-react';
import { resolveGuildContext } from '../../utils/guildContext';

export default function Announcements() {
    const { user } = useAuth();
    const { t } = useTranslation();
    const toast = useToast();
    const guildName = resolveGuildContext(user);

    const [announcements, setAnnouncements] = useState<Announcement[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [detailModal, setDetailModal] = useState<Announcement | null>(null);
    const [formData, setFormData] = useState({ title: '', content: '', type: 'general' });
    const [creating, setCreating] = useState(false);

    // Filters
    const [filters, setFilters] = useState({ type: '', author: '', dateFrom: '', dateTo: '' });
    const [showFilters, setShowFilters] = useState(false);
    const [skip, setSkip] = useState(0);
    const LIMIT = 10;

    // Infinite scroll
    const observer = useRef<IntersectionObserver | null>(null);
    const lastElementRef = useCallback((node: HTMLDivElement | null) => {
        if (loadingMore) return;
        if (observer.current) observer.current.disconnect();
        observer.current = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasMore) {
                loadMore();
            }
        });
        if (node) observer.current.observe(node);
    }, [loadingMore, hasMore]);

    // Check if user is admin or leader (simple check for now, backend enforces security)
    const canCreate = user?.is_superuser || user?.guild_rank === 'Alpha Warbringer' || user?.guild_rank === 'Bloodhowl Marshal';

    const loadData = async (reset = false) => {
        try {
            const currentSkip = reset ? 0 : skip;
            if (reset) {
                setLoading(true);
                setSkip(0);
            } else {
                setLoadingMore(true);
            }
            
            if (!guildName) {
                setAnnouncements([]);
                return;
            }
            const data = await guildApi.getAnnouncements(currentSkip, LIMIT, guildName);
            
            if (reset) {
                setAnnouncements(data);
            } else {
                setAnnouncements(prev => [...prev, ...data]);
            }
            
            setHasMore(data.length === LIMIT);
            if (!reset) setSkip(prev => prev + LIMIT);
        } catch (error) {
            console.error("Failed to load announcements", error);
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    };

    const loadMore = () => {
        if (!loadingMore && hasMore) {
            loadData(false);
        }
    };

    useEffect(() => {
        loadData(true);
    }, [filters, guildName]);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreating(true);
        try {
            if (!guildName) throw new Error('Missing guild context');
            await guildApi.createAnnouncement(formData, guildName);
            setShowModal(false);
            setFormData({ title: '', content: '', type: 'general' });
            loadData(true);
            toast.success('Announcement created successfully!');
        } catch (error) {
            console.error("Failed to create announcement", error);
            toast.error("Failed to create announcement");
        } finally {
            setCreating(false);
        }
    };

    const applyFilters = (data: Announcement[]) => {
        return data.filter(ann => {
            if (filters.type && ann.type !== filters.type) return false;
            if (filters.author && !ann.author?.username.toLowerCase().includes(filters.author.toLowerCase())) return false;
            if (filters.dateFrom && new Date(ann.created_at) < new Date(filters.dateFrom)) return false;
            if (filters.dateTo && new Date(ann.created_at) > new Date(filters.dateTo)) return false;
            return true;
        });
    };

    const clearFilters = () => {
        setFilters({ type: '', author: '', dateFrom: '', dateTo: '' });
    };

    const filteredAnnouncements = applyFilters(announcements);

    return (
        <div className="space-y-8">
            <div className="border-b-4 border-gradient-to-r from-amber-500 to-amber-400 pb-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <h1 className="text-4xl lg:text-5xl font-bold text-slate-100 flex items-center gap-3">
                        <div className="p-3 bg-gradient-to-br from-amber-500/20 to-amber-600/20 rounded-lg">
                            <Megaphone className="w-8 h-8 lg:w-10 lg:h-10 text-amber-400" />
                        </div>
                        {t('guild.announcements')}
                    </h1>

                    <div className="flex gap-3">
                        <button
                            onClick={() => setShowFilters(!showFilters)}
                            className="flex items-center gap-2 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 hover:border-amber-500/40 text-slate-200 px-4 py-3 rounded-lg transition-all font-semibold text-base"
                        >
                            <Filter className="w-5 h-5" />
                            <span className="hidden xs:inline">{t('guild.filters')}</span>
                        </button>

                        {canCreate && (
                            <button
                                onClick={() => setShowModal(true)}
                                className="flex items-center gap-2 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white px-4 py-3 rounded-lg transition-all font-semibold text-base shadow-lg hover:shadow-amber-500/30"
                            >
                                <Plus className="w-5 h-5" />
                                <span className="hidden xs:inline">{t('guild.create')}</span>
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {/* Filters Panel */}
            {showFilters && (
                <div className="bg-gradient-to-b from-slate-800/40 to-slate-900/40 border-2 border-slate-700/60 rounded-xl p-6 backdrop-blur-sm">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                        <div>
                            <label className="block text-xs font-bold text-slate-300 mb-2 uppercase tracking-wider">{t('guild.type')}</label>
                            <select
                                value={filters.type}
                                onChange={e => setFilters({ ...filters, type: e.target.value })}
                                className="w-full bg-slate-950/60 border-2 border-slate-700/60 hover:border-slate-600 rounded-lg p-3 text-slate-200 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all"
                            >
                                <option value="">{t('common.filter')}...</option>
                                <option value="general">{t('guild.types.general')}</option>
                                <option value="hunt">{t('guild.types.hunt')}</option>
                                <option value="contest">{t('guild.types.contest')}</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-xs font-bold text-slate-300 mb-2 uppercase tracking-wider">{t('guild.author')}</label>
                            <input
                                type="text"
                                value={filters.author}
                                onChange={e => setFilters({ ...filters, author: e.target.value })}
                                placeholder={t('common.search') + '...'}
                                className="w-full bg-slate-950/60 border-2 border-slate-700/60 hover:border-slate-600 rounded-lg p-3 text-slate-200 text-sm placeholder-slate-500 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-bold text-slate-300 mb-2 uppercase tracking-wider">{t('guild.filterByDate')} (desde)</label>
                            <input
                                type="date"
                                value={filters.dateFrom}
                                onChange={e => setFilters({ ...filters, dateFrom: e.target.value })}
                                className="w-full bg-slate-950/60 border-2 border-slate-700/60 hover:border-slate-600 rounded-lg p-3 text-slate-200 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-bold text-slate-300 mb-2 uppercase tracking-wider">{t('guild.filterByDate')} (hasta)</label>
                            <input
                                type="date"
                                value={filters.dateTo}
                                onChange={e => setFilters({ ...filters, dateTo: e.target.value })}
                                className="w-full bg-slate-950/60 border-2 border-slate-700/60 hover:border-slate-600 rounded-lg p-3 text-slate-200 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all"
                            />
                        </div>
                    </div>

                    <div className="mt-5 flex justify-end">
                        <button
                            onClick={clearFilters}
                            className="text-sm text-slate-400 hover:text-amber-400 hover:bg-slate-800/50 flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all font-medium"
                        >
                            <X className="w-4 h-4" />
                            {t('guild.clearFilters')}
                        </button>
                    </div>
                </div>
            )}

            {loading ? (
                <div className="flex justify-center p-12">
                    <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
                </div>
            ) : (
                <div className="space-y-6">
                    {filteredAnnouncements.map((ann, index) => {
                        const isLast = index === filteredAnnouncements.length - 1;
                        return (
                            <div 
                                key={ann.id} 
                                ref={isLast ? lastElementRef : null}
                                onClick={() => setDetailModal(ann)}
                                className="bg-gradient-to-br from-slate-800/60 to-slate-900/80 border-2 border-slate-700/80 rounded-xl overflow-hidden shadow-2xl hover:shadow-amber-500/20 hover:border-amber-500/60 transition-all duration-300 cursor-pointer animate-fade-in group hover:scale-[1.01]"
                            >
                                <div className={`h-2 w-full transition-all duration-300 ${ann.type === 'contest' ? 'bg-gradient-to-r from-purple-500 to-purple-400' :
                                    ann.type === 'hunt' ? 'bg-gradient-to-r from-red-500 to-red-400' :
                                        'bg-gradient-to-r from-amber-500 to-amber-400'
                                    }`} />
                                <div className="p-8">
                                    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-6">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-3 mb-3">
                                                <span className={`inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider whitespace-nowrap ${ann.type === 'contest' ? 'bg-purple-900/70 text-purple-200 ring-1 ring-purple-500/60' :
                                                    ann.type === 'hunt' ? 'bg-red-900/70 text-red-200 ring-1 ring-red-500/60' :
                                                        'bg-amber-900/70 text-amber-200 ring-1 ring-amber-500/60'
                                                    }`}>
                                                    {t(`guild.types.${ann.type}`)}
                                                </span>
                                            </div>
                                            <h2 className="text-2xl lg:text-3xl font-bold text-slate-100 leading-tight group-hover:text-amber-300 transition-colors break-words">{ann.title}</h2>
                                        </div>
                                        <div className="text-sm text-slate-400 flex flex-col gap-2 lg:text-right whitespace-nowrap">
                                            <div className="flex items-center gap-2 lg:justify-end">
                                                <CalendarClock className="w-4 h-4 flex-shrink-0 text-amber-500/70" />
                                                <span className="font-medium">{new Date(ann.created_at).toLocaleDateString()}</span>
                                            </div>
                                            <div className="flex items-center gap-2 lg:justify-end">
                                                <User className="w-4 h-4 flex-shrink-0 text-amber-500/70" />
                                                <span className="text-slate-300 font-semibold">
                                                    {ann.author?.is_superuser ? '👑 Ray On' : ann.author?.username}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="prose prose-invert prose-sm max-w-none text-slate-300 line-clamp-4 leading-relaxed text-base">
                                        {ann.content}
                                    </div>
                                    
                                    <div className="mt-4 pt-4 border-t border-slate-700/50 flex items-center justify-end">
                                        <span className="text-xs text-slate-500 group-hover:text-amber-500/70 transition-colors">Click para ver más →</span>
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {loadingMore && (
                        <div className="flex justify-center p-4">
                            <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                        </div>
                    )}

                    {!hasMore && announcements.length > 0 && (
                        <div className="text-center py-8">
                            <p className="text-sm text-slate-500 font-medium">{t('guild.noMoreResults')}</p>
                        </div>
                    )}

                    {!loading && announcements.length === 0 && (
                        <div className="text-center py-16">
                            <div className="flex justify-center mb-4">
                                <Megaphone className="w-16 h-16 text-slate-600 opacity-50" />
                            </div>
                            <p className="text-slate-400 text-lg font-medium">{t('guild.noAnnouncements')}</p>
                            <p className="text-slate-500 text-sm mt-2">Vuelve más tarde para nuevos anuncios</p>
                        </div>
                    )}
                </div>
            )}

            {/* Detail Modal */}
            {detailModal && (
                <div 
                    className="fixed inset-0 bg-black/90 backdrop-blur-md z-50 flex items-center justify-center p-4"
                    onClick={() => setDetailModal(null)}
                >
                    <div 
                        className="bg-gradient-to-b from-slate-800 to-slate-900 border-2 border-slate-700/80 rounded-2xl w-full max-w-4xl shadow-2xl max-h-[85vh] overflow-y-auto"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className={`h-3 w-full ${detailModal.type === 'contest' ? 'bg-gradient-to-r from-purple-500 to-purple-400' :
                            detailModal.type === 'hunt' ? 'bg-gradient-to-r from-red-500 to-red-400' :
                                'bg-gradient-to-r from-amber-500 to-amber-400'
                            }`} />
                        
                        <div className="sticky top-0 bg-slate-900/95 backdrop-blur p-8 border-b-2 border-slate-700/50 flex items-start justify-between">
                            <div className="flex-1 pr-4">
                                <div className="flex items-center gap-3 mb-4">
                                    <span className={`inline-block px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${detailModal.type === 'contest' ? 'bg-purple-900/70 text-purple-200 ring-1 ring-purple-500/60' :
                                        detailModal.type === 'hunt' ? 'bg-red-900/70 text-red-200 ring-1 ring-red-500/60' :
                                            'bg-amber-900/70 text-amber-200 ring-1 ring-amber-500/60'
                                        }`}>
                                        {t(`guild.types.${detailModal.type}`)}
                                    </span>
                                </div>
                                <h3 className="text-3xl lg:text-4xl font-bold text-slate-100 leading-tight break-words">{detailModal.title}</h3>
                                <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6 mt-4 text-sm">
                                    <div className="flex items-center gap-2 text-slate-400">
                                        <User className="w-5 h-5 text-amber-500/70" />
                                        <span className="font-semibold text-slate-300">
                                            {detailModal.author?.is_superuser ? '👑 Ray On' : detailModal.author?.username}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2 text-slate-400">
                                        <CalendarClock className="w-5 h-5 text-amber-500/70" />
                                        <span className="font-medium">{new Date(detailModal.created_at).toLocaleString()}</span>
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={() => setDetailModal(null)}
                                className="text-slate-400 hover:text-slate-200 hover:bg-slate-800 p-2 rounded-lg transition-colors flex-shrink-0"
                            >
                                <X className="w-6 h-6" />
                            </button>
                        </div>

                        <div className="p-8 lg:p-10">
                            <div className="prose prose-invert prose-lg max-w-none text-slate-300 whitespace-pre-line leading-relaxed">
                                {detailModal.content}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black/90 backdrop-blur-md z-50 flex items-center justify-center p-4">
                    <div className="bg-gradient-to-b from-slate-800 to-slate-900 border-2 border-slate-700/80 rounded-2xl w-full max-w-2xl shadow-2xl">
                        <div className="p-8 border-b-2 border-slate-700/50">
                            <div className="flex items-center gap-3 mb-2">
                                <Megaphone className="w-6 h-6 text-amber-500" />
                                <h3 className="text-2xl font-bold text-slate-100">{t('guild.create')} {t('guild.announcements')}</h3>
                            </div>
                            <p className="text-slate-400 text-sm">{t('guild.announcements')} ({t('guild.create')})</p>
                        </div>

                        <form onSubmit={handleCreate} className="p-8 space-y-6">
                            <div>
                                <label className="block text-sm font-bold text-slate-300 mb-3 uppercase tracking-wider">{t('guild.title')}</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.title}
                                    onChange={e => setFormData({ ...formData, title: e.target.value })}
                                    placeholder="Escribir el título del anuncio..."
                                    className="w-full bg-slate-950/80 border-2 border-slate-700/60 rounded-lg px-4 py-3 text-slate-200 placeholder-slate-500 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all text-base"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-bold text-slate-300 mb-3 uppercase tracking-wider">{t('guild.type')}</label>
                                <select
                                    value={formData.type}
                                    onChange={e => setFormData({ ...formData, type: e.target.value })}
                                    className="w-full bg-slate-950/80 border-2 border-slate-700/60 rounded-lg px-4 py-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all text-base"
                                >
                                    <option value="general">{t('guild.types.general')}</option>
                                    <option value="contest">{t('guild.types.contest')}</option>
                                    <option value="hunt">{t('guild.types.hunt')}</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-bold text-slate-300 mb-3 uppercase tracking-wider">{t('guild.content')}</label>
                                <textarea
                                    required
                                    rows={8}
                                    value={formData.content}
                                    onChange={e => setFormData({ ...formData, content: e.target.value })}
                                    placeholder="Escribir el contenido del anuncio..."
                                    className="w-full bg-slate-950/80 border-2 border-slate-700/60 rounded-lg px-4 py-3 text-slate-200 placeholder-slate-500 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all font-mono text-sm leading-relaxed"
                                />
                            </div>

                            <div className="flex justify-end gap-4 mt-8 pt-6 border-t border-slate-700/50">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="px-6 py-2.5 text-slate-300 hover:text-slate-100 hover:bg-slate-800/50 rounded-lg font-semibold transition-all text-base"
                                >
                                    {t('guild.cancel')}
                                </button>
                                <button
                                    type="submit"
                                    disabled={creating}
                                    className="bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white px-6 py-2.5 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-all text-base shadow-lg hover:shadow-amber-500/30"
                                >
                                    {creating ? <span className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> {t('guild.loading')}</span> : t('guild.create')}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
