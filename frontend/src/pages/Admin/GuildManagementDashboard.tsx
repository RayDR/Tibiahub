import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { guildManagementApi, GuildMember, GuildSyncResult } from '../../services/guildManagement';
import api from '../../services/api';
import { AssistanceBanner } from '../../components/workspace/WorkspacePrimitives';
import {
    Users, Shield, Edit2, Trash2,
    Save, X, Loader2, RefreshCw, Bell, Calendar,
} from 'lucide-react';

type Tab = 'members' | 'events' | 'announcements';

interface GuildEvent {
    id: number;
    title: string;
    description?: string;
    start_time: string;
    end_time?: string;
    is_deleted?: boolean;
}

interface GuildAnnouncement {
    id: number;
    title: string;
    content: string;
    created_at: string;
    is_deleted?: boolean;
}

export default function GuildManagementDashboard() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const toast = useToast();
    const [searchParams] = useSearchParams();
    const assistedGuild = (searchParams.get('guild') || '').trim();

    // Guild selection stage
    const [selectedGuild] = useState<string | null>(assistedGuild || null);

    // Content state
    const [activeTab, setActiveTab] = useState<Tab>('members');
    const [loadingContent, setLoadingContent] = useState(false);
    const [members, setMembers] = useState<GuildMember[]>([]);
    const [events, setEvents] = useState<GuildEvent[]>([]);
    const [announcements, setAnnouncements] = useState<GuildAnnouncement[]>([]);

    // Member edit state
    const [editingUser, setEditingUser] = useState<number | null>(null);
    const [editForm, setEditForm] = useState<Partial<GuildMember>>({});
    const [editingCharacter, setEditingCharacter] = useState<number | null>(null);
    const [newCharacterName, setNewCharacterName] = useState('');
    const [syncing, setSyncing] = useState(false);
    const [syncResult, setSyncResult] = useState<GuildSyncResult | null>(null);

    useEffect(() => {
        if (!user?.is_superuser && user?.guild_rank !== 'Alpha Warbringer' && user?.guild_rank !== 'Bloodhowl Marshal') {
            navigate('/guild');
        }
    }, [user, navigate]);

    useEffect(() => { if (assistedGuild) void loadMembers(assistedGuild); }, [assistedGuild]);

    const loadMembers = async (guildName: string) => {
        setLoadingContent(true);
        try {
            const data = await guildManagementApi.getUsers(0, 200, {
                guild_name: user?.is_superuser ? guildName : undefined,
                include_inactive: false,
                exclude_test_accounts: true,
            });
            setMembers(data);
        } catch {
            toast.error('Failed to load members');
        } finally {
            setLoadingContent(false);
        }
    };

    const loadEvents = async () => {
        if (!selectedGuild) return;
        setLoadingContent(true);
        try {
            const token = localStorage.getItem('token');
            const response = await api.get('/guild/events', {
                headers: { Authorization: `Bearer ${token}` },
                params: { limit: 50, guild_name: selectedGuild },
            });
            setEvents(response.data || []);
        } catch {
            setEvents([]);
        } finally {
            setLoadingContent(false);
        }
    };

    const loadAnnouncements = async () => {
        if (!selectedGuild) return;
        setLoadingContent(true);
        try {
            const token = localStorage.getItem('token');
            const response = await api.get('/guild/announcements', {
                headers: { Authorization: `Bearer ${token}` },
                params: { limit: 50, guild_name: selectedGuild },
            });
            setAnnouncements(response.data || []);
        } catch {
            setAnnouncements([]);
        } finally {
            setLoadingContent(false);
        }
    };

    const switchTab = (tab: Tab) => {
        setActiveTab(tab);
        if (tab === 'events') void loadEvents();
        else if (tab === 'announcements') void loadAnnouncements();
    };

    const handleSyncGuild = async () => {
        if (!selectedGuild) return;
        setSyncing(true);
        try {
            const result = await guildManagementApi.syncGuild(selectedGuild);
            setSyncResult(result);
            await loadMembers(selectedGuild);
            toast.success('Guild synced successfully!');
        } catch {
            toast.error('Failed to sync guild');
        } finally {
            setSyncing(false);
        }
    };

    const handleUpdateUser = async (userId: number) => {
        try {
            await guildManagementApi.updateUser(userId, editForm);
            setEditingUser(null);
            setEditForm({});
            if (selectedGuild) await loadMembers(selectedGuild);
            toast.success('User updated');
        } catch {
            toast.error('Failed to update user');
        }
    };

    const handleDeleteUser = async (userId: number, username: string) => {
        if (!window.confirm(`Delete user "${username}"? This cannot be undone.`)) return;
        try {
            await guildManagementApi.deleteUser(userId);
            if (selectedGuild) await loadMembers(selectedGuild);
            toast.success(`User "${username}" deleted`);
        } catch {
            toast.error('Failed to delete user');
        }
    };

    const handleUpdateCharacter = async (userId: number) => {
        if (!newCharacterName.trim()) { toast.error('Enter a character name'); return; }
        try {
            const result = await guildManagementApi.updateUserCharacter(userId, newCharacterName.trim());
            if (result.validation_passed) {
                toast.success(`Character updated to "${result.character_name}"`);
            } else {
                toast.warning?.(`Character updated but validation failed: ${result.validation_message || 'Unknown'}`);
            }
            setEditingCharacter(null);
            setNewCharacterName('');
            if (selectedGuild) await loadMembers(selectedGuild);
        } catch (error: any) {
            toast.error(error.response?.data?.detail || 'Failed to update character');
        }
    };

    const handleDeleteEvent = async (eventId: number) => {
        if (!window.confirm('Delete this event?')) return;
        try {
            const token = localStorage.getItem('token');
            await api.delete(`/guild/events/${eventId}`, {
                headers: { Authorization: `Bearer ${token}` },
                data: { reason: 'Deleted by admin' },
            });
            toast.success('Event deleted');
            void loadEvents();
        } catch {
            toast.error('Failed to delete event');
        }
    };

    const handleDeleteAnnouncement = async (announcementId: number) => {
        if (!window.confirm('Delete this announcement?')) return;
        try {
            const token = localStorage.getItem('token');
            await api.delete(`/guild/announcements/${announcementId}`, {
                headers: { Authorization: `Bearer ${token}` },
                data: { reason: 'Deleted by admin' },
            });
            toast.success('Announcement deleted');
            void loadAnnouncements();
        } catch {
            toast.error('Failed to delete announcement');
        }
    };

    // ── Guild selector stage ──────────────────────────────────────────────────
    if (!selectedGuild) {
        return <Navigate to="/admin/guilds" replace />;
    }

    // ── Guild management view ─────────────────────────────────────────────────
    return (
        <div className="space-y-4">
            <AssistanceBanner guildName={selectedGuild} />
            {/* Header with guild name and back */}
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-3">
                        <Shield className="w-5 h-5 text-amber-500" />
                        <div>
                            <h1 className="text-xl font-semibold text-slate-100">{selectedGuild}</h1>
                            <p className="text-sm text-slate-400">Guild management — members, events, announcements</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleSyncGuild}
                            disabled={syncing}
                            className="flex items-center gap-2 rounded-md bg-amber-600 px-3 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50"
                        >
                            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
                            {syncing ? 'Syncing…' : 'Sync from Tibia'}
                        </button>
                        <button
                            onClick={() => navigate('/admin/guilds')}
                            className="rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-400 hover:text-slate-200"
                        >
                            ← Change guild
                        </button>
                    </div>
                </div>
                {syncResult && (
                    <div className="mt-3 rounded bg-green-900/20 border border-green-700/40 px-4 py-2 text-sm text-green-300 flex flex-wrap gap-4">
                        <span>Synced: <strong>{syncResult.synced_users}</strong></span>
                        <span>Updated chars: <strong>{syncResult.updated_characters}</strong></span>
                        <span>Total members: <strong>{syncResult.total_members}</strong></span>
                    </div>
                )}
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-slate-700 bg-slate-900/30 rounded-t-lg">
                {([
                    { id: 'members', label: 'Members', icon: Users },
                    { id: 'events', label: 'Events', icon: Calendar },
                    { id: 'announcements', label: 'Announcements', icon: Bell },
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

            {/* Tab content */}
            {loadingContent ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                </div>
            ) : activeTab === 'members' ? (
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
                        <span className="text-sm text-slate-400">{members.length} members</span>
                        <button
                            onClick={() => void loadMembers(selectedGuild)}
                            className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 border border-slate-700 rounded px-2 py-1"
                        >
                            <RefreshCw className="w-3 h-3" /> Refresh
                        </button>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-slate-950/50">
                                <tr>
                                    <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-slate-400">User</th>
                                    <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Rank</th>
                                    <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Characters</th>
                                    <th className="text-left p-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Status</th>
                                    <th className="text-right p-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {members.length === 0 ? (
                                    <tr><td colSpan={5} className="p-8 text-center text-slate-500">No members found.</td></tr>
                                ) : members.map((member) => (
                                    <tr key={member.id} className="border-t border-slate-800 hover:bg-slate-950/30 group">
                                        <td className="p-3">
                                            {editingUser === member.id ? (
                                                <input
                                                    type="text"
                                                    value={editForm.username || member.username}
                                                    onChange={(e) => setEditForm({ ...editForm, username: e.target.value })}
                                                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200 w-full"
                                                />
                                            ) : (
                                                <div>
                                                    <div className="font-medium text-slate-200 text-sm">{member.username}</div>
                                                    <div className="text-xs text-slate-500">{member.email || 'No email'}</div>
                                                    {member.is_superuser && (
                                                        <span className="text-xs bg-red-900/50 text-red-300 px-1.5 py-0.5 rounded">Admin</span>
                                                    )}
                                                </div>
                                            )}
                                        </td>
                                        <td className="p-3">
                                            {editingUser === member.id ? (
                                                <input
                                                    type="text"
                                                    value={editForm.guild_rank || member.guild_rank || ''}
                                                    onChange={(e) => setEditForm({ ...editForm, guild_rank: e.target.value })}
                                                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200 w-full"
                                                />
                                            ) : (
                                                <span className="text-xs bg-slate-800 text-slate-300 px-2 py-1 rounded">
                                                    {member.guild_rank || 'No Rank'}
                                                </span>
                                            )}
                                        </td>
                                        <td className="p-3">
                                            {editingCharacter === member.id ? (
                                                <div className="flex items-center gap-2">
                                                    <input
                                                        type="text"
                                                        value={newCharacterName}
                                                        onChange={(e) => setNewCharacterName(e.target.value)}
                                                        placeholder="Character name"
                                                        className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200 flex-1"
                                                    />
                                                    <button onClick={() => void handleUpdateCharacter(member.id)} className="p-1.5 text-green-400 hover:bg-green-900/20 rounded">
                                                        <Save className="w-3.5 h-3.5" />
                                                    </button>
                                                    <button onClick={() => { setEditingCharacter(null); setNewCharacterName(''); }} className="p-1.5 text-slate-400 hover:bg-slate-800 rounded">
                                                        <X className="w-3.5 h-3.5" />
                                                    </button>
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-2 group">
                                                    <div className="flex-1 text-sm text-slate-300">
                                                        {member.characters.length > 0
                                                            ? member.characters.map((c) => `${c.character_name}${c.level ? ` (${c.level})` : ''}`).join(', ')
                                                            : <span className="text-slate-500 italic">None</span>
                                                        }
                                                    </div>
                                                    <button
                                                        onClick={() => { setEditingCharacter(member.id); setNewCharacterName(member.characters[0]?.character_name || ''); }}
                                                        className="p-1 text-blue-400 hover:bg-blue-900/20 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                                                    >
                                                        <Edit2 className="w-3 h-3" />
                                                    </button>
                                                </div>
                                            )}
                                        </td>
                                        <td className="p-3">
                                            <span className={`text-xs px-2 py-1 rounded ${member.is_active ? 'bg-green-900/40 text-green-300' : 'bg-slate-800 text-slate-500'}`}>
                                                {member.is_active ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td className="p-3">
                                            <div className="flex items-center justify-end gap-1">
                                                {editingUser === member.id ? (
                                                    <>
                                                        <button onClick={() => void handleUpdateUser(member.id)} className="p-1.5 text-green-400 hover:bg-green-900/20 rounded">
                                                            <Save className="w-3.5 h-3.5" />
                                                        </button>
                                                        <button onClick={() => { setEditingUser(null); setEditForm({}); }} className="p-1.5 text-slate-400 hover:bg-slate-800 rounded">
                                                            <X className="w-3.5 h-3.5" />
                                                        </button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <button onClick={() => { setEditingUser(member.id); setEditForm(member); }} className="p-1.5 text-blue-400 hover:bg-blue-900/20 rounded" title="Edit">
                                                            <Edit2 className="w-3.5 h-3.5" />
                                                        </button>
                                                        <button
                                                            onClick={() => void handleDeleteUser(member.id, member.username)}
                                                            disabled={member.id === user?.id}
                                                            className="p-1.5 text-red-400 hover:bg-red-900/20 rounded disabled:opacity-30" title="Delete"
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : activeTab === 'events' ? (
                <div className="space-y-2">
                    {events.length === 0 ? (
                        <div className="text-center py-12 text-slate-500 bg-slate-900/50 border border-slate-700 rounded-lg">No events found.</div>
                    ) : events.map((event) => (
                        <div key={event.id} className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 flex items-start justify-between gap-4">
                            <div>
                                <div className="font-medium text-slate-100 text-sm">{event.title}</div>
                                {event.description && <div className="text-xs text-slate-400 mt-1 line-clamp-2">{event.description}</div>}
                                <div className="text-xs text-slate-500 mt-1">{new Date(event.start_time).toLocaleString()}</div>
                            </div>
                            <button
                                onClick={() => void handleDeleteEvent(event.id)}
                                className="flex-shrink-0 p-1.5 text-red-400 hover:bg-red-900/20 rounded"
                                title="Delete event"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="space-y-2">
                    {announcements.length === 0 ? (
                        <div className="text-center py-12 text-slate-500 bg-slate-900/50 border border-slate-700 rounded-lg">No announcements found.</div>
                    ) : announcements.map((a) => (
                        <div key={a.id} className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 flex items-start justify-between gap-4">
                            <div>
                                <div className="font-medium text-slate-100 text-sm">{a.title}</div>
                                <div className="text-xs text-slate-400 mt-1 line-clamp-2">{a.content}</div>
                                <div className="text-xs text-slate-500 mt-1">{new Date(a.created_at).toLocaleString()}</div>
                            </div>
                            <button
                                onClick={() => void handleDeleteAnnouncement(a.id)}
                                className="flex-shrink-0 p-1.5 text-red-400 hover:bg-red-900/20 rounded"
                                title="Delete announcement"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
