import { useState, useEffect } from 'react';
import { guildManagementApi } from '../../services/guildManagement';
import { Settings as SettingsIcon, Save, RefreshCw, CheckCircle, XCircle } from 'lucide-react';

interface SystemSettings {
    tibia_validation_enabled: boolean;
    tibia_validation_strict: boolean;
    discord_webhook_url: string;
    discord_auto_post: boolean;
    guild_raffles_enabled: boolean;
    guild_contests_enabled: boolean;
}

export default function AdminSettings() {
    const [settings, setSettings] = useState<SystemSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        try {
            const data = await guildManagementApi.getSettings();
            setSettings(data);
        } catch (error) {
            console.error('Failed to load settings:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        if (!settings) return;
        
        setSaving(true);
        setMessage(null);
        
        try {
            await guildManagementApi.updateSettings(settings);
            setMessage({ type: 'success', text: 'Settings saved successfully!' });
        } catch (error) {
            console.error('Failed to save settings:', error);
            setMessage({ type: 'error', text: 'Failed to save settings' });
        } finally {
            setSaving(false);
        }
    };

    const updateSetting = (key: keyof SystemSettings, value: any) => {
        if (settings) {
            setSettings({ ...settings, [key]: value });
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <RefreshCw className="w-8 h-8 animate-spin text-red-500" />
            </div>
        );
    }

    if (!settings) {
        return <div className="text-center text-slate-400">Failed to load settings</div>;
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-serif text-slate-100 flex items-center gap-3">
                    <SettingsIcon className="w-8 h-8 text-red-500" />
                    System Settings
                </h1>
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 bg-red-600 hover:bg-red-500 disabled:bg-slate-700 disabled:text-slate-500 text-white px-6 py-2.5 rounded-md transition-colors font-medium"
                >
                    <Save className="w-4 h-4" />
                    {saving ? 'Saving...' : 'Save Changes'}
                </button>
            </div>

            {message && (
                <div className={`p-4 rounded-lg border flex items-center gap-3 ${
                    message.type === 'success' 
                        ? 'bg-green-900/20 border-green-700/50 text-green-400' 
                        : 'bg-red-900/20 border-red-700/50 text-red-400'
                }`}>
                    {message.type === 'success' ? (
                        <CheckCircle className="w-5 h-5" />
                    ) : (
                        <XCircle className="w-5 h-5" />
                    )}
                    {message.text}
                </div>
            )}

            <div className="space-y-6">
                {/* Tibia Validation Settings */}
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-slate-100 mb-4">Tibia Character Validation</h2>
                    
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-slate-200">Enable Validation</h3>
                                <p className="text-sm text-slate-400">Validate character names against Tibia API during registration</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.tibia_validation_enabled}
                                    onChange={(e) => updateSetting('tibia_validation_enabled', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-red-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                            </label>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-slate-200">Strict Mode</h3>
                                <p className="text-sm text-slate-400">Block registration if Tibia API is unavailable</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.tibia_validation_strict}
                                    onChange={(e) => updateSetting('tibia_validation_strict', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-red-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                            </label>
                        </div>
                    </div>
                </div>

                {/* Discord Integration Settings */}
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-slate-100 mb-4">Discord Integration</h2>
                    
                    <div className="space-y-4">
                        <div>
                            <label className="block font-medium text-slate-200 mb-2">Webhook URL</label>
                            <input
                                type="text"
                                value={settings.discord_webhook_url}
                                onChange={(e) => updateSetting('discord_webhook_url', e.target.value)}
                                placeholder="https://discord.com/api/webhooks/..."
                                className="w-full bg-slate-950 border border-slate-700 rounded-md px-4 py-2.5 text-slate-200 focus:border-red-500 focus:outline-none"
                            />
                            <p className="text-xs text-slate-500 mt-1">
                                Get your webhook URL from Discord Server Settings → Integrations → Webhooks
                            </p>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-slate-200">Auto-Post Announcements</h3>
                                <p className="text-sm text-slate-400">Automatically post new announcements to Discord</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.discord_auto_post}
                                    onChange={(e) => updateSetting('discord_auto_post', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-red-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
                            </label>
                        </div>
                    </div>
                </div>

                {/* Guild Features */}
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-slate-100 mb-4">Guild Feature Toggles</h2>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-slate-200">Guild Raffles</h3>
                                <p className="text-sm text-slate-400">Enable or disable raffle views and registration flows</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.guild_raffles_enabled}
                                    onChange={(e) => updateSetting('guild_raffles_enabled', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-red-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                            </label>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-slate-200">Guild Contests</h3>
                                <p className="text-sm text-slate-400">Enable or disable contest references in guild event flows</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.guild_contests_enabled}
                                    onChange={(e) => updateSetting('guild_contests_enabled', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-red-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
