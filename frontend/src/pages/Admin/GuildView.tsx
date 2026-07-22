/**
 * Admin Guild View – read-only simulation of the guild as seen by any member.
 * Admins select a guild, then browse announcements, events, and members in read-only mode.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { guildManagementApi } from '../../services/guildManagement';
import api from '../../services/api';
import {
    Bell, Calendar, ChevronRight, Eye, Loader2, Shield, Users,
} from 'lucide-react';

type Tab = 'announcements' | 'events' | 'members';

interface GuildEvent {
    id: number;
    title: string;
    description?: string;
    start_time: string;
    end_time?: string;
    location?: string;
}

interface Announcement {
    id: number;
    title: string;
    content: string;
    created_at: string;
}

interface Member {
    id: number;
    username: string;
    guild_rank?: string;
    is_active: boolean;
    characters: { character_name: string; level?: number; vocation?: string }[];
}

export default function GuildView() {
    const { user } = useAuth();
    const navigate = useNavigate();

    const [guilds, setGuilds] = useState<string[]>([]);
    const [selectedGuild, setSelectedGuild] = useState<string | null>(null);
    const [loadingGuilds, setLoadingGuilds] = useState(true);

    const [activeTab, setActiveTab] = useState<Tab>('announcements');
    const [loadingContent, setLoadingContent] = useState(false);
    const [announcements, setAnnouncements] = useState<Announcement[]>([]);
    const [events, setEvents] = useState<GuildEvent[]>([]);
    const [members, setMembers] = useState<Member[]>([]);

    useEffect(() => {
        if (!user?.is_superuser) navigate('/guild');
    }, [user, navigate]);

    useEffect(() => {
        const load = async () => {
            setLoadingGuilds(true);
            try {
                const data = await guildManagementApi.getGuilds();
                setGuilds(data.filter((g) => Boolean(g?.trim())));
            } catch { /* ignore */ }
            finally { setLoadingGuilds(false); }
        };
        void load();
    }, []);

    const selectGuild = (name: string) => {
        setSelectedGuild(name);
        setActiveTab('announcements');
        void loadAnnouncements(name);
    };

    const loadAnnouncements = async (guildName = selectedGuild) => {
        setLoadingContent(true);
        try {
            if (!guildName) return;
            const res = await api.get('/guild/announcements', { params: { limit: 20, guild_name: guildName } });
            setAnnouncements(res.data || []);
        } catch { setAnnouncements([]); }
        finally { setLoadingContent(false); }
    };

    const loadEvents = async (guildName = selectedGuild) => {
        setLoadingContent(true);
        try {
            if (!guildName) return;
            const res = await api.get('/guild/events', { params: { limit: 20, guild_name: guildName } });
            setEvents(res.data || []);
        } catch { setEvents([]); }
        finally { setLoadingContent(false); }
    };

    const loadMembers = async (guildName: string) => {
        setLoadingContent(true);
        try {
            const data = await guildManagementApi.getUsers(0, 100, {
                guild_name: guildName,
                include_inactive: false,
                exclude_test_accounts: true,
            });
            setMembers(data);
        } catch { setMembers([]); }
        finally { setLoadingContent(false); }
    };

    const switchTab = (tab: Tab) => {
        setActiveTab(tab);
        if (tab === 'announcements') void loadAnnouncements();
        else if (tab === 'events') void loadEvents();
        else if (tab === 'members' && selectedGuild) void loadMembers(selectedGuild);
    };

    // Guild selector
    if (!selectedGuild) {
        return (
            <div className="space-y-4">
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-1">
                        <Eye className="w-5 h-5 text-amber-500" />
                        <h1 className="text-xl font-semibold text-slate-100">Guild Preview</h1>
                    </div>
                    <p className="text-sm text-slate-400">Read-only view of any guild, as any member would see it.</p>
                </div>

                {loadingGuilds ? (
                    <div className="flex items-center justify-center py-16">
                        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
                    </div>
                ) : guilds.length === 0 ? (
                    <div className="text-center py-16 text-slate-500">No guilds found.</div>
                ) : (
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {guilds.map((guildName) => (
                            <button
                                key={guildName}
                                onClick={() => selectGuild(guildName)}
                                className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-900/50 p-4 text-left hover:border-amber-500/50 hover:bg-amber-500/5 transition-colors group"
                            >
                                <div className="flex items-center gap-3">
                                    <Shield className="w-8 h-8 text-amber-500/60 group-hover:text-amber-400" />
                                    <div>
                                        <div className="font-medium text-slate-100">{guildName}</div>
                                        <div className="text-xs text-slate-500 mt-0.5">View read-only</div>
                                    </div>
                                </div>
                                <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-amber-400" />
                            </button>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-3">
                        <Eye className="w-5 h-5 text-amber-500" />
                        <div>
                            <div className="flex items-center gap-2">
                                <h1 className="text-xl font-semibold text-slate-100">{selectedGuild}</h1>
                                <span className="text-xs bg-amber-900/40 text-amber-300 px-2 py-0.5 rounded border border-amber-700/40">
                                    Read-only preview
                                </span>
                            </div>
                            <p className="text-sm text-slate-400">Viewing as admin — no actions available.</p>
                        </div>
                    </div>
                    <button
                        onClick={() => setSelectedGuild(null)}
                        className="rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400 hover:text-slate-200"
                    >
                        ← Change guild
                    </button>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-slate-700">
                {([
                    { id: 'announcements', label: 'Announcements', icon: Bell },
                    { id: 'events', label: 'Events', icon: Calendar },
                    { id: 'members', label: 'Members', icon: Users },
                ] as { id: Tab; label: string; icon: any }[]).map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => switchTab(id)}
                        className={`flex items-center gap-2 px-4 py-2.5 border-b-2 text-sm font-medium transition-colors ${
                            activeTab === id
                                ? 'border-amber-500 text-amber-400'
                                : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        <Icon className="w-4 h-4" />
                        {label}
                    </button>
                ))}
            </div>

            {loadingContent ? (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                </div>
            ) : activeTab === 'announcements' ? (
                <div className="space-y-3">
                    {announcements.length === 0 ? (
                        <div className="text-center py-12 text-slate-500 bg-slate-900/50 border border-slate-700 rounded-lg">No announcements.</div>
                    ) : announcements.map((a) => (
                        <div key={a.id} className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                            <div className="font-medium text-slate-100 text-sm">{a.title}</div>
                            <div className="text-sm text-slate-400 mt-1">{a.content}</div>
                            <div className="text-xs text-slate-600 mt-2">{new Date(a.created_at).toLocaleString()}</div>
                        </div>
                    ))}
                </div>
            ) : activeTab === 'events' ? (
                <div className="space-y-3">
                    {events.length === 0 ? (
                        <div className="text-center py-12 text-slate-500 bg-slate-900/50 border border-slate-700 rounded-lg">No events.</div>
                    ) : events.map((e) => (
                        <div key={e.id} className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                            <div className="font-medium text-slate-100 text-sm">{e.title}</div>
                            {e.description && <div className="text-sm text-slate-400 mt-1">{e.description}</div>}
                            <div className="flex gap-4 text-xs text-slate-500 mt-2">
                                <span>{new Date(e.start_time).toLocaleString()}</span>
                                {e.location && <span>📍 {e.location}</span>}
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg overflow-hidden">
                    <table className="w-full">
                        <thead className="bg-slate-950/50">
                            <tr>
                                <th className="p-3 text-left text-xs uppercase text-slate-400">Member</th>
                                <th className="p-3 text-left text-xs uppercase text-slate-400">Rank</th>
                                <th className="p-3 text-left text-xs uppercase text-slate-400">Character</th>
                            </tr>
                        </thead>
                        <tbody>
                            {members.length === 0 ? (
                                <tr><td colSpan={3} className="p-8 text-center text-slate-500">No members found.</td></tr>
                            ) : members.map((m) => (
                                <tr key={m.id} className="border-t border-slate-800">
                                    <td className="p-3 text-sm text-slate-200">{m.username}</td>
                                    <td className="p-3 text-sm">
                                        <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                                            {m.guild_rank || '—'}
                                        </span>
                                    </td>
                                    <td className="p-3 text-xs text-slate-400">
                                        {m.characters.length > 0
                                            ? m.characters.map((c) => `${c.character_name}${c.level ? ` (${c.level})` : ''}`).join(', ')
                                            : '—'
                                        }
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
