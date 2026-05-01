// Profile Page - User can view and edit their own profile
import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useNavigate } from 'react-router-dom';
import { User, Shield, Mail, Calendar, Edit2, Save, X, Loader2 } from 'lucide-react';
import api from '../services/api';

interface ProfileData {
    username: string;
    email: string;
    tibia_character_name: string;
    guild_rank?: string;
    vocation?: string;
    level?: number;
    is_active: boolean;
    join_date?: string;
    created_at: string;
}

export default function Profile() {
    const { user, updateUser } = useAuth();
    const toast = useToast();
    const navigate = useNavigate();
    
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [editing, setEditing] = useState(false);
    const [profileData, setProfileData] = useState<ProfileData | null>(null);
    const [formData, setFormData] = useState({
        email: '',
        tibia_character_name: '',
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
                email: response.data.email || '',
                tibia_character_name: response.data.tibia_character_name || '',
            });
        } catch (error) {
            console.error('Failed to load profile:', error);
            toast.error('Failed to load profile');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const response = await api.put('/profile/me', formData);
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
                email: profileData.email || '',
                tibia_character_name: profileData.tibia_character_name || '',
            });
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
            </div>
        );
    }

    if (!profileData) {
        return (
            <div className="text-center text-slate-400 py-20">
                Failed to load profile data
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl md:text-4xl font-serif text-slate-100 mb-2 flex items-center gap-3">
                    <User className="w-8 h-8 md:w-10 md:h-10 text-amber-500" />
                    My Profile
                </h1>
                <p className="text-slate-400 text-sm md:text-base">View and manage your account information</p>
            </div>

            {/* Profile Card */}
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg overflow-hidden">
                {/* Header with Edit Button */}
                <div className="p-4 md:p-6 border-b border-slate-700 flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-slate-100">Account Information</h2>
                    {!editing ? (
                        <button
                            onClick={() => setEditing(true)}
                            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-3 md:px-4 py-2 rounded-md transition-colors text-sm font-medium"
                        >
                            <Edit2 className="w-4 h-4" />
                            <span className="hidden sm:inline">Edit</span>
                        </button>
                    ) : (
                        <div className="flex gap-2">
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                className="flex items-center gap-2 bg-green-600 hover:bg-green-500 disabled:bg-slate-700 disabled:text-slate-500 text-white px-3 md:px-4 py-2 rounded-md transition-colors text-sm font-medium"
                            >
                                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                <span className="hidden sm:inline">Save</span>
                            </button>
                            <button
                                onClick={handleCancel}
                                disabled={saving}
                                className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white px-3 md:px-4 py-2 rounded-md transition-colors text-sm font-medium"
                            >
                                <X className="w-4 h-4" />
                                <span className="hidden sm:inline">Cancel</span>
                            </button>
                        </div>
                    )}
                </div>

                {/* Profile Fields */}
                <div className="p-4 md:p-6 space-y-6">
                    {/* Username - Read only */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">
                            Username
                        </label>
                        <div className="bg-slate-950/50 border border-slate-700 rounded px-3 py-2 text-slate-300">
                            {profileData.username}
                        </div>
                        <p className="text-xs text-slate-500 mt-1">Username cannot be changed</p>
                    </div>

                    {/* Email */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">
                            <Mail className="w-4 h-4 inline mr-1" />
                            Email
                        </label>
                        {editing ? (
                            <input
                                type="email"
                                value={formData.email}
                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-amber-500"
                                placeholder="your.email@example.com"
                            />
                        ) : (
                            <div className="bg-slate-950/50 border border-slate-700 rounded px-3 py-2 text-slate-300">
                                {profileData.email || 'Not set'}
                            </div>
                        )}
                    </div>

                    {/* Tibia Character */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">
                            <Shield className="w-4 h-4 inline mr-1" />
                            Tibia Character
                        </label>
                        <div className="bg-slate-950/50 border border-slate-700 rounded px-3 py-2 text-slate-300">
                            {profileData.tibia_character_name}
                        </div>
                        <p className="text-xs text-slate-500 mt-1">Contact an admin to change your linked character</p>
                    </div>

                    {/* Vocation */}
                    {profileData.vocation && (
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">
                                Class / Vocation
                            </label>
                            <div className="bg-slate-950/50 border border-slate-700 rounded px-3 py-2 text-slate-300">
                                {profileData.vocation}
                                {profileData.level && <span className="text-slate-500"> (Level {profileData.level})</span>}
                            </div>
                        </div>
                    )}

                    {/* Guild Rank */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">
                            Guild Rank
                        </label>
                        <div className="bg-slate-950/50 border border-slate-700 rounded px-3 py-2">
                            <span className="text-slate-300">{profileData.guild_rank || 'Not Ranked'}</span>
                        </div>
                    </div>

                    {/* Account Info */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">
                                <Calendar className="w-4 h-4 inline mr-1" />
                                Member Since
                            </label>
                            <div className="bg-slate-950/50 border border-slate-700 rounded px-3 py-2 text-slate-300 text-sm">
                                {profileData.join_date 
                                    ? new Date(profileData.join_date).toLocaleDateString()
                                    : new Date(profileData.created_at).toLocaleDateString()
                                }
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">
                                Status
                            </label>
                            <div className="bg-slate-950/50 border border-slate-700 rounded px-3 py-2">
                                {profileData.is_active ? (
                                    <span className="text-xs bg-green-900/50 text-green-300 px-2 py-1 rounded">Active</span>
                                ) : (
                                    <span className="text-xs bg-slate-800 text-slate-500 px-2 py-1 rounded">Inactive</span>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
