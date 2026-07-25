// Profile Page - User can view and edit their own profile
import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { User, Shield, Mail, Calendar, Edit2, Save, X, Loader2, Link2, Lock, Tag, BadgeInfo } from 'lucide-react';
import api from '../services/api';

interface ProfileData {
    username: string;
    display_name?: string;
    title?: string;
    email: string;
    avatar_url?: string;
    tibia_character_name: string;
    guild_rank?: string;
    guild_name?: string;
    world_name?: string;
    residence?: string;
    vocation?: string;
    level?: number;
    achievement_points?: number;
    tibia_status?: string;
    tibia_last_error?: string;
    is_active: boolean;
    join_date?: string;
    created_at: string;
}

export default function Profile() {
    const { updateUser } = useAuth();
    const toast = useToast();

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [editing, setEditing] = useState(false);
    const [profileData, setProfileData] = useState<ProfileData | null>(null);
    const [formData, setFormData] = useState({
        display_name: '',
        title: '',
        email: '',
        avatar_url: '',
        tibia_character_name: '',
        current_password: '',
        new_password: '',
        confirm_password: '',
    });

    useEffect(() => {
        loadProfile();
    }, []);

    const loadProfile = async () => {
        setLoading(true);
        try {
            const response = await api.get('/profile/me');
            setProfileData(response.data);
            setFormData({
                display_name: response.data.display_name || '',
                title: response.data.title || '',
                email: response.data.email || '',
                avatar_url: response.data.avatar_url || '',
                tibia_character_name: response.data.tibia_character_name || '',
                current_password: '',
                new_password: '',
                confirm_password: '',
            });
        } catch (error) {
            console.error('Failed to load profile:', error);
            toast.error('Failed to load profile');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        if (formData.new_password && formData.new_password !== formData.confirm_password) {
            toast.error('New password and confirmation do not match');
            return;
        }
        if (formData.new_password && !formData.current_password) {
            toast.error('Current password is required to set a new password');
            return;
        }

        setSaving(true);
        try {
            const payload: Record<string, string> = {
                display_name: formData.display_name,
                title: formData.title,
                email: formData.email,
                avatar_url: formData.avatar_url,
            };
            if (formData.new_password) {
                payload.current_password = formData.current_password;
                payload.new_password = formData.new_password;
            }

            const response = await api.put('/profile/me', payload);
            setProfileData(response.data);
            setEditing(false);

            // Update user context
            if (updateUser) {
                updateUser(response.data);
            }

            toast.success('Profile updated successfully!');
        } catch (error: any) {
            console.error('Failed to update profile:', error);
            const errorMsg = error.response?.data?.detail || 'Failed to update profile';
            toast.error(errorMsg);
        } finally {
            setSaving(false);
        }
    };

    const handleCancel = () => {
        setEditing(false);
        if (profileData) {
            setFormData({
                display_name: profileData.display_name || '',
                title: profileData.title || '',
                email: profileData.email || '',
                avatar_url: profileData.avatar_url || '',
                tibia_character_name: profileData.tibia_character_name || '',
                current_password: '',
                new_password: '',
                confirm_password: '',
            });
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    if (!profileData) {
        return (
            <div className="text-center text-content-muted py-20">
                Failed to load profile data
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl md:text-4xl font-serif text-content-primary mb-2 flex items-center gap-3">
                    <User className="w-8 h-8 md:w-10 md:h-10 text-primary" />
                    My Profile
                </h1>
                <p className="text-content-muted text-sm md:text-base">View and manage your account information</p>
            </div>

            {/* Profile Card */}
            <div className="app-surface rounded-lg overflow-hidden">
                {/* Header with Edit Button */}
                <div className="p-4 md:p-6 border-b border-line flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-content-primary">Account Information</h2>
                    {!editing ? (
                        <button
                            onClick={() => setEditing(true)}
                            className="flex items-center gap-2 app-button-primary px-3 md:px-4 py-2 rounded-md transition-colors text-sm font-medium"
                        >
                            <Edit2 className="w-4 h-4" />
                            <span className="hidden sm:inline">Edit</span>
                        </button>
                    ) : (
                        <div className="flex gap-2">
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                className="flex items-center gap-2 bg-success hover:brightness-110 disabled:bg-surface-raised disabled:text-content-muted text-content-on-primary px-3 md:px-4 py-2 rounded-md transition-colors text-sm font-medium"
                            >
                                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                <span className="hidden sm:inline">Save</span>
                            </button>
                            <button
                                onClick={handleCancel}
                                disabled={saving}
                                className="flex items-center gap-2 app-button-ghost disabled:opacity-50 text-content-primary px-3 md:px-4 py-2 rounded-md transition-colors text-sm font-medium"
                            >
                                <X className="w-4 h-4" />
                                <span className="hidden sm:inline">Cancel</span>
                            </button>
                        </div>
                    )}
                </div>

                {/* Profile Fields */}
                <div className="p-4 md:p-6 space-y-6">
                    {/* Avatar URL */}
                    <div>
                        <label className="block text-sm font-medium text-content-muted mb-2">
                            <Link2 className="w-4 h-4 inline mr-1" />
                            Avatar URL
                        </label>
                        {editing ? (
                            <input
                                type="url"
                                value={formData.avatar_url}
                                onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })}
                                className="app-input w-full px-3 py-2"
                                placeholder="https://.../avatar.png"
                            />
                        ) : (
                            <div className="bg-surface-raised border border-line rounded px-3 py-2 text-content-primary break-all">
                                {profileData.avatar_url || 'Not set'}
                            </div>
                        )}
                        {(editing ? formData.avatar_url : profileData.avatar_url) && (
                            <div className="mt-3 h-16 w-16 overflow-hidden rounded-full border border-line bg-surface-raised">
                                <img
                                    src={editing ? formData.avatar_url : profileData.avatar_url}
                                    alt="Avatar"
                                    className="h-full w-full object-cover"
                                    onError={(event) => {
                                        (event.target as HTMLImageElement).style.display = 'none';
                                    }}
                                />
                            </div>
                        )}
                    </div>

                    {/* Display Name */}
                    <div>
                        <label className="block text-sm font-medium text-content-muted mb-2">
                            <Tag className="w-4 h-4 inline mr-1" />
                            Display Name
                        </label>
                        {editing ? (
                            <input
                                type="text"
                                value={formData.display_name}
                                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                                className="app-input w-full px-3 py-2"
                                placeholder="How others will see you (leave blank to use username)"
                                maxLength={100}
                            />
                        ) : (
                            <div className="bg-surface-raised border border-line rounded px-3 py-2 text-content-primary">
                                {profileData.display_name || <span className="text-content-muted italic">Not set</span>}
                            </div>
                        )}
                    </div>

                    {/* Title */}
                    <div>
                        <label className="block text-sm font-medium text-content-muted mb-2">
                            <BadgeInfo className="w-4 h-4 inline mr-1" />
                            Title / Bio Line
                        </label>
                        {editing ? (
                            <input
                                type="text"
                                value={formData.title}
                                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                                className="app-input w-full px-3 py-2"
                                placeholder="e.g. Guild Master, Veteran Hunter..."
                                maxLength={100}
                            />
                        ) : (
                            <div className="bg-surface-raised border border-line rounded px-3 py-2 text-content-primary">
                                {profileData.title || <span className="text-content-muted italic">Not set</span>}
                            </div>
                        )}
                    </div>

                    {/* Username - Read only */}
                    <div>
                        <label className="block text-sm font-medium text-content-muted mb-2">
                            Username
                        </label>
                        <div className="bg-surface-raised border border-line rounded px-3 py-2 text-content-primary">
                            {profileData.username}
                        </div>
                        <p className="text-xs text-content-muted mt-1">Username cannot be changed</p>
                    </div>

                    {/* Email */}
                    <div>
                        <label className="block text-sm font-medium text-content-muted mb-2">
                            <Mail className="w-4 h-4 inline mr-1" />
                            Email
                        </label>
                        {editing ? (
                            <input
                                type="email"
                                value={formData.email}
                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                className="app-input w-full px-3 py-2"
                                placeholder="your.email@example.com"
                            />
                        ) : (
                            <div className="bg-surface-raised border border-line rounded px-3 py-2 text-content-primary">
                                {profileData.email || 'Not set'}
                            </div>
                        )}
                    </div>

                    {/* Tibia Character */}
                    <div>
                        <label className="block text-sm font-medium text-content-muted mb-2">
                            <Shield className="w-4 h-4 inline mr-1" />
                            Tibia Character
                        </label>
                        <div className="bg-surface-raised border border-line rounded px-3 py-2 text-content-primary">
                            {profileData.tibia_character_name}
                        </div>
                        <p className="text-xs text-content-muted mt-1">Contact an admin to change your linked character</p>
                    </div>

                    {/* Vocation */}
                    {profileData.vocation && (
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-2">
                                Class / Vocation
                            </label>
                            <div className="bg-surface-base/50 border border-line rounded px-3 py-2 text-content-secondary">
                                {profileData.vocation}
                                {profileData.level && <span className="text-content-muted"> (Level {profileData.level})</span>}
                            </div>
                        </div>
                    )}

                    {/* Guild Rank */}
                    <div>
                        <label className="block text-sm font-medium text-content-secondary mb-2">
                            Guild Rank
                        </label>
                        <div className="bg-surface-base/50 border border-line rounded px-3 py-2">
                            <span className="text-content-secondary">{profileData.guild_rank || 'Not Ranked'}</span>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-2">Guild</label>
                            <div className="bg-surface-base/50 border border-line rounded px-3 py-2 text-content-secondary">
                                {profileData.guild_name || 'Not available'}
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-2">World</label>
                            <div className="bg-surface-base/50 border border-line rounded px-3 py-2 text-content-secondary">
                                {profileData.world_name || 'Not available'}
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-2">Residence</label>
                            <div className="bg-surface-base/50 border border-line rounded px-3 py-2 text-content-secondary">
                                {profileData.residence || 'Not available'}
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-content-secondary mb-2">Tibia Status</label>
                        <div className="bg-surface-base/50 border border-line rounded px-3 py-2 text-content-secondary">
                            Status: {profileData.tibia_status || 'unknown'}
                            {profileData.achievement_points !== undefined && profileData.achievement_points !== null ? ` · Achievement points: ${profileData.achievement_points}` : ''}
                        </div>
                        {profileData.tibia_last_error && (
                            <p className="text-xs text-danger mt-2">{profileData.tibia_last_error}</p>
                        )}
                    </div>

                    {/* Account Info */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-2">
                                <Calendar className="w-4 h-4 inline mr-1" />
                                Member Since
                            </label>
                            <div className="bg-surface-base/50 border border-line rounded px-3 py-2 text-content-secondary text-sm">
                                {profileData.join_date
                                    ? new Date(profileData.join_date).toLocaleDateString()
                                    : new Date(profileData.created_at).toLocaleDateString()
                                }
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-content-secondary mb-2">
                                Status
                            </label>
                            <div className="bg-surface-base/50 border border-line rounded px-3 py-2">
                                {profileData.is_active ? (
                                    <span className="text-xs bg-success/50 text-success px-2 py-1 rounded">Active</span>
                                ) : (
                                    <span className="text-xs bg-surface text-content-muted px-2 py-1 rounded">Inactive</span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Password Change */}
                    {editing && (
                        <div className="rounded-lg border border-line bg-surface-base/40 p-4">
                            <h3 className="mb-3 text-sm font-semibold text-content-primary flex items-center gap-2">
                                <Lock className="w-4 h-4 text-primary" />
                                Change Password (Optional)
                            </h3>
                            <div className="space-y-3">
                                <input
                                    type="password"
                                    value={formData.current_password}
                                    onChange={(e) => setFormData({ ...formData, current_password: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded px-3 py-2 text-content-primary focus:outline-none focus:border-primary"
                                    placeholder="Current password"
                                />
                                <input
                                    type="password"
                                    value={formData.new_password}
                                    onChange={(e) => setFormData({ ...formData, new_password: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded px-3 py-2 text-content-primary focus:outline-none focus:border-primary"
                                    placeholder="New password"
                                />
                                <input
                                    type="password"
                                    value={formData.confirm_password}
                                    onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded px-3 py-2 text-content-primary focus:outline-none focus:border-primary"
                                    placeholder="Confirm new password"
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
