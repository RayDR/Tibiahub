// Guild Management Dashboard Component
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { guildManagementApi, GuildMember, SystemStats, TibiaAPIStatus, SystemSettings, GuildSyncResult } from '../../services/guildManagement';
import { 
    Users, Settings, Activity, Shield, AlertCircle, 
    CheckCircle, XCircle, RefreshCw, Edit2, Trash2, 
    Save, X, Loader2, Database, Globe
} from 'lucide-react';

export default function GuildManagementDashboard() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const toast = useToast();

    const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'settings'>('overview');
    const [loading, setLoading] = useState(true);
    const [users, setUsers] = useState<GuildMember[]>([]);
    const [stats, setStats] = useState<SystemStats | null>(null);
    const [tibiaStatus, setTibiaStatus] = useState<TibiaAPIStatus | null>(null);
    const [settings, setSettings] = useState<SystemSettings | null>(null);
    const [editingUser, setEditingUser] = useState<number | null>(null);
    const [editForm, setEditForm] = useState<Partial<GuildMember>>({});
    const [editingCharacter, setEditingCharacter] = useState<number | null>(null);
    const [newCharacterName, setNewCharacterName] = useState<string>('');
    const [syncResult, setSyncResult] = useState<GuildSyncResult | null>(null);
    const [syncing, setSyncing] = useState(false);

    // Check if user has permission
    useEffect(() => {
        if (!user?.is_superuser && user?.guild_rank !== 'Alpha Warbringer' && user?.guild_rank !== 'Bloodhowl Marshal') {
            navigate('/guild');
        }
    }, [user, navigate]);

    useEffect(() => {
        loadAllData();
    }, []);

    const loadAllData = async () => {
        setLoading(true);
        try {
            const [usersData, statsData, statusData, settingsData] = await Promise.all([
                guildManagementApi.getUsers(),
                guildManagementApi.getStats(),
                guildManagementApi.getTibiaAPIStatus(),
                guildManagementApi.getSettings(),
            ]);
            setUsers(usersData);
            setStats(statsData);
            setTibiaStatus(statusData);
            setSettings(settingsData);
        } catch (error) {
            console.error('Failed to load data:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSyncGuild = async () => {
        setSyncing(true);
        try {
            const result = await guildManagementApi.syncGuild();
            setSyncResult(result);
            loadAllData(); // Reload data after sync
            toast.success('Guild synced successfully!');
        } catch (error) {
            console.error('Failed to sync guild:', error);
            toast.error('Failed to sync guild. Please try again.');
        } finally {
            setSyncing(false);
        }
    };

    const handleUpdateUser = async (userId: number) => {
        try {
            await guildManagementApi.updateUser(userId, editForm);
            setEditingUser(null);
            setEditForm({});
            loadAllData();
            toast.success('User updated successfully!');
        } catch (error) {
            console.error('Failed to update user:', error);
            toast.error('Failed to update user');
        }
    };

    const handleDeleteUser = async (userId: number, username: string) => {
        const confirmed = window.confirm(`Are you sure you want to delete user "${username}"? This action cannot be undone.`);
        if (!confirmed) return;

        try {
            await guildManagementApi.deleteUser(userId);
            loadAllData();
            toast.success(`User "${username}" deleted successfully`);
        } catch (error) {
            console.error('Failed to delete user:', error);
            toast.error('Failed to delete user');
        }
    };
    const handleUpdateCharacter = async (userId: number) => {
        if (!newCharacterName.trim()) {
            toast.error('Please enter a character name');
            return;
        }

        try {
            const result = await guildManagementApi.updateUserCharacter(userId, newCharacterName.trim());
            
            if (result.validation_passed) {
                toast.success(`Character updated to "${result.character_name}" - Validation passed!`);
            } else {
                toast.warning(`Character updated to "${result.character_name}", but validation failed: ${result.validation_message || 'Unknown error'}`);
            }
            
            setEditingCharacter(null);
            setNewCharacterName('');
            loadAllData();
        } catch (error: any) {
            console.error('Failed to update character:', error);
            const errorMsg = error.response?.data?.detail || 'Failed to update character';
            toast.error(errorMsg);
        }
    };
    const handleToggleSetting = async (key: keyof SystemSettings, value: boolean) => {
        try {
            const updated = await guildManagementApi.updateSettings({ [key]: value });
            setSettings(updated);
        } catch (error) {
            console.error('Failed to update settings:', error);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'online': return 'text-green-400';
            case 'offline': return 'text-red-400';
            case 'degraded': return 'text-yellow-400';
            default: return 'text-gray-400';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'online': return <CheckCircle className="w-5 h-5" />;
            case 'offline': return <XCircle className="w-5 h-5" />;
            case 'degraded': return <AlertCircle className="w-5 h-5" />;
            default: return <Activity className="w-5 h-5" />;
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
            </div>
        );
    }

    return (
        <div className="container mx-auto px-4 py-8 max-w-7xl">
            <div className="mb-8">
                <h1 className="text-4xl font-serif text-slate-100 mb-2 flex items-center gap-3">
                    <Shield className="w-10 h-10 text-amber-500" />
                    Guild Management
                </h1>
                <p className="text-slate-400">Manage your guild members, settings, and synchronization with Tibia</p>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 mb-6 border-b border-slate-700">
                {[
                    { id: 'overview', label: 'Overview', icon: Activity },
                    { id: 'users', label: 'Members', icon: Users },
                    { id: 'settings', label: 'Settings', icon: Settings },
                ].map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id as any)}
                        className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                            activeTab === tab.id
                                ? 'border-amber-500 text-amber-500'
                                : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                    >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Overview Tab */}
            {activeTab === 'overview' && (
                <div className="space-y-6">
                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-5">
                            <div className="text-sm text-slate-400 mb-1">Total Members</div>
                            <div className="text-3xl font-bold text-slate-100">{stats?.total_users || 0}</div>
                            <div className="text-xs text-slate-500 mt-1">{stats?.active_users || 0} active</div>
                        </div>
                        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-5">
                            <div className="text-sm text-slate-400 mb-1">Admin Users</div>
                            <div className="text-3xl font-bold text-amber-500">{stats?.admin_users || 0}</div>
                        </div>
                        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-5">
                            <div className="text-sm text-slate-400 mb-1">Linked Characters</div>
                            <div className="text-3xl font-bold text-slate-100">{stats?.total_characters_linked || 0}</div>
                        </div>
                        <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-5">
                            <div className="text-sm text-slate-400 mb-1">Guild Ranks</div>
                            <div className="text-3xl font-bold text-slate-100">{stats?.guild_ranks.length || 0}</div>
                        </div>
                    </div>

                    {/* Tibia API Status */}
                    <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6">
                        <h3 className="text-lg font-semibold text-slate-100 mb-4 flex items-center gap-2">
                            <Database className="w-5 h-5 text-amber-500" />
                            Tibia API Status
                        </h3>
                        {tibiaStatus && (
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className={getStatusColor(tibiaStatus.status)}>
                                        {getStatusIcon(tibiaStatus.status)}
                                    </div>
                                    <div>
                                        <div className="font-medium text-slate-200">{tibiaStatus.status.toUpperCase()}</div>
                                        <div className="text-sm text-slate-400">{tibiaStatus.message}</div>
                                        {tibiaStatus.latency_ms && (
                                            <div className="text-xs text-slate-500 mt-1">Latency: {tibiaStatus.latency_ms.toFixed(0)}ms</div>
                                        )}
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => navigate('/admin/api-monitor')}
                                        className="flex items-center gap-2 bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-md transition-colors text-sm font-medium"
                                    >
                                        <Globe className="w-4 h-4" />
                                        Monitor APIs
                                    </button>
                                    <button
                                        onClick={handleSyncGuild}
                                        disabled={syncing}
                                        className="flex items-center gap-2 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 disabled:text-slate-500 text-white px-4 py-2 rounded-md transition-colors text-sm font-medium"
                                    >
                                        <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
                                        Sync with Tibia
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Sync Result */}
                    {syncResult && (
                        <div className="bg-green-900/20 border border-green-700/50 rounded-lg p-6">
                            <h3 className="text-lg font-semibold text-green-400 mb-4">Sync Successful!</h3>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                <div>
                                    <div className="text-slate-400">Total Members</div>
                                    <div className="text-2xl font-bold text-slate-100">{syncResult.total_members}</div>
                                </div>
                                <div>
                                    <div className="text-slate-400">Synced Users</div>
                                    <div className="text-2xl font-bold text-green-400">{syncResult.synced_users}</div>
                                </div>
                                <div>
                                    <div className="text-slate-400">Updated Characters</div>
                                    <div className="text-2xl font-bold text-blue-400">{syncResult.updated_characters}</div>
                                </div>
                                <div>
                                    <div className="text-slate-400">New Characters</div>
                                    <div className="text-2xl font-bold text-purple-400">{syncResult.new_characters}</div>
                                </div>
                            </div>
                            {syncResult.invalid_users.length > 0 && (
                                <div className="mt-4 pt-4 border-t border-green-700/30">
                                    <div className="text-sm text-yellow-400 mb-2">⚠️ Invalid Users Found:</div>
                                    <div className="space-y-1">
                                        {syncResult.invalid_users.map((u) => (
                                            <div key={u.user_id} className="text-xs text-slate-400">
                                                • {u.username} ({u.character_name}): {u.reason}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Guild Ranks Distribution */}
                    <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6">
                        <h3 className="text-lg font-semibold text-slate-100 mb-4">Guild Rank Distribution</h3>
                        <div className="space-y-2">
                            {stats?.guild_ranks.map((rank) => (
                                <div key={rank.rank} className="flex items-center justify-between py-2 px-3 bg-slate-950/50 rounded">
                                    <span className="text-slate-300">{rank.rank}</span>
                                    <span className="font-semibold text-amber-500">{rank.count}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* Users Tab */}
            {activeTab === 'users' && (
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-slate-950/50">
                                <tr>
                                    <th className="text-left p-4 text-sm font-semibold text-slate-400">User</th>
                                    <th className="text-left p-4 text-sm font-semibold text-slate-400">Email</th>
                                    <th className="text-left p-4 text-sm font-semibold text-slate-400">Rank</th>
                                    <th className="text-left p-4 text-sm font-semibold text-slate-400">Characters</th>
                                    <th className="text-left p-4 text-sm font-semibold text-slate-400">Status</th>
                                    <th className="text-right p-4 text-sm font-semibold text-slate-400">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((member) => (
                                    <tr key={member.id} className="border-t border-slate-800 hover:bg-slate-950/30 group"
>
                                        <td className="p-4">
                                            {editingUser === member.id ? (
                                                <input
                                                    type="text"
                                                    value={editForm.username || member.username}
                                                    onChange={(e) => setEditForm({ ...editForm, username: e.target.value })}
                                                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200"
                                                />
                                            ) : (
                                                <div>
                                                    <div className="font-medium text-slate-200">{member.username}</div>
                                                    {member.is_superuser && (
                                                        <span className="text-xs bg-red-900/50 text-red-300 px-2 py-0.5 rounded">Admin</span>
                                                    )}
                                                </div>
                                            )}
                                        </td>
                                        <td className="p-4 text-sm text-slate-400">
                                            {editingUser === member.id ? (
                                                <input
                                                    type="email"
                                                    value={editForm.email || member.email || ''}
                                                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                                                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200"
                                                />
                                            ) : (
                                                member.email || 'N/A'
                                            )}
                                        </td>
                                        <td className="p-4">
                                            {editingUser === member.id ? (
                                                <input
                                                    type="text"
                                                    value={editForm.guild_rank || member.guild_rank || ''}
                                                    onChange={(e) => setEditForm({ ...editForm, guild_rank: e.target.value })}
                                                    className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200"
                                                />
                                            ) : (
                                                <span className="text-sm bg-slate-800 text-slate-300 px-2 py-1 rounded">
                                                    {member.guild_rank || 'No Rank'}
                                                </span>
                                            )}
                                        </td>
                                        <td className="p-4">
                                            {editingCharacter === member.id ? (
                                                <div className="flex items-center gap-2">
                                                    <input
                                                        type="text"
                                                        value={newCharacterName}
                                                        onChange={(e) => setNewCharacterName(e.target.value)}
                                                        placeholder="Character name"
                                                        className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-sm text-slate-200 flex-1"
                                                    />
                                                    <button
                                                        onClick={() => handleUpdateCharacter(member.id)}
                                                        className="p-1.5 text-green-400 hover:bg-green-900/20 rounded transition-colors"
                                                        title="Save character"
                                                    >
                                                        <Save className="w-4 h-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => {
                                                            setEditingCharacter(null);
                                                            setNewCharacterName('');
                                                        }}
                                                        className="p-1.5 text-slate-400 hover:bg-slate-800 rounded transition-colors"
                                                        title="Cancel"
                                                    >
                                                        <X className="w-4 h-4" />
                                                    </button>
                                                </div>
                                            ) : (
                                                <div className="flex items-center gap-2">
                                                    <div className="flex-1">
                                                        {member.characters.length > 0 ? (
                                                            <div className="space-y-1">
                                                                {member.characters.map((char) => (
                                                                    <div key={char.character_name} className="text-sm text-slate-300">
                                                                        {char.character_name}
                                                                        {char.level && <span className="text-slate-500"> (Lv {char.level})</span>}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        ) : (
                                                            <span className="text-sm text-slate-500 italic">No characters</span>
                                                        )}
                                                    </div>
                                                    <button
                                                        onClick={() => {
                                                            setEditingCharacter(member.id);
                                                            setNewCharacterName(member.characters[0]?.character_name || '');
                                                        }}
                                                        className="p-1.5 text-blue-400 hover:bg-blue-900/20 rounded transition-colors opacity-0 group-hover:opacity-100 transition-opacity"
                                                        title="Edit character"
                                                    >
                                                        <Edit2 className="w-3 h-3" />
                                                    </button>
                                                </div>
                                            )}
                                        </td>
                                        <td className="p-4">
                                            {member.is_active ? (
                                                <span className="text-xs bg-green-900/50 text-green-300 px-2 py-1 rounded">Active</span>
                                            ) : (
                                                <span className="text-xs bg-slate-800 text-slate-500 px-2 py-1 rounded">Inactive</span>
                                            )}
                                        </td>
                                        <td className="p-4">
                                            <div className="flex items-center justify-end gap-2">
                                                {editingUser === member.id ? (
                                                    <>
                                                        <button
                                                            onClick={() => handleUpdateUser(member.id)}
                                                            className="p-1.5 text-green-400 hover:bg-green-900/20 rounded transition-colors"
                                                            title="Save"
                                                        >
                                                            <Save className="w-4 h-4" />
                                                        </button>
                                                        <button
                                                            onClick={() => {
                                                                setEditingUser(null);
                                                                setEditForm({});
                                                            }}
                                                            className="p-1.5 text-slate-400 hover:bg-slate-800 rounded transition-colors"
                                                            title="Cancel"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <button
                                                            onClick={() => {
                                                                setEditingUser(member.id);
                                                                setEditForm(member);
                                                            }}
                                                            className="p-1.5 text-blue-400 hover:bg-blue-900/20 rounded transition-colors"
                                                            title="Edit"
                                                        >
                                                            <Edit2 className="w-4 h-4" />
                                                        </button>
                                                        <button
                                                            onClick={() => handleDeleteUser(member.id, member.username)}
                                                            className="p-1.5 text-red-400 hover:bg-red-900/20 rounded transition-colors"
                                                            title="Delete"
                                                            disabled={member.id === user?.id}
                                                        >
                                                            <Trash2 className="w-4 h-4" />
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
            )}

            {/* Settings Tab */}
            {activeTab === 'settings' && settings && (
                <div className="space-y-6">
                    <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6">
                        <h3 className="text-lg font-semibold text-slate-100 mb-4">Validation Settings</h3>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between p-4 bg-slate-950/50 rounded">
                                <div>
                                    <div className="font-medium text-slate-200">Tibia Character Validation</div>
                                    <div className="text-sm text-slate-400 mt-1">
                                        Validate character names using Tibia API during registration
                                    </div>
                                </div>
                                <button
                                    onClick={() => handleToggleSetting('tibia_validation_enabled', !settings.tibia_validation_enabled)}
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                        settings.tibia_validation_enabled ? 'bg-amber-600' : 'bg-slate-700'
                                    }`}
                                >
                                    <span
                                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                            settings.tibia_validation_enabled ? 'translate-x-6' : 'translate-x-1'
                                        }`}
                                    />
                                </button>
                            </div>

                            {settings.tibia_validation_enabled && (
                                <div className="flex items-center justify-between p-4 bg-slate-950/50 rounded border-l-4 border-amber-500">
                                    <div>
                                        <div className="font-medium text-slate-200">Strict Mode</div>
                                        <div className="text-sm text-slate-400 mt-1">
                                            Block registration when Tibia API is down (flexible mode allows registration without validation)
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleToggleSetting('tibia_validation_strict', !settings.tibia_validation_strict)}
                                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                            settings.tibia_validation_strict ? 'bg-red-600' : 'bg-slate-700'
                                        }`}
                                    >
                                        <span
                                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                                settings.tibia_validation_strict ? 'translate-x-6' : 'translate-x-1'
                                            }`}
                                        />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>

                    {tibiaStatus && tibiaStatus.status === 'offline' && settings.tibia_validation_strict && (
                        <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg p-4">
                            <div className="flex items-start gap-3">
                                <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                                <div>
                                    <div className="font-medium text-yellow-400">Warning</div>
                                    <div className="text-sm text-slate-300 mt-1">
                                        Tibia API is offline and strict mode is enabled. Users cannot register with characters.
                                        Consider disabling strict mode temporarily.
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
