import { useState, useEffect } from 'react';
import { guildManagementApi } from '../../services/guildManagement';
import { Settings as SettingsIcon, Save, RefreshCw, CheckCircle, XCircle } from 'lucide-react';
import EmailDiagnosticsPanel from '../../components/admin/EmailDiagnosticsPanel';

interface SystemSettings {
    tibia_validation_enabled: boolean;
    tibia_validation_strict: boolean;
    discord_webhook_url: string;
    discord_auto_post: boolean;
    guild_raffles_enabled: boolean;
    guild_contests_enabled: boolean;
    cyclopedia_category_images: Record<string, string>;
}

const CREATURE_CATEGORY_KEYS = [
    'amphibic', 'aquatic', 'bird', 'construct', 'demon', 'dragon', 'elemental',
    'fey', 'giant', 'human', 'humanoid', 'lycanthrope', 'magical', 'mammal', 'undead', 'beast',
];

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

    const updateCategoryImage = (category: string, value: string) => {
        if (!settings) return;
        setSettings({
            ...settings,
            cyclopedia_category_images: {
                ...(settings.cyclopedia_category_images || {}),
                [category]: value,
            },
        });
    };

    const handleCategoryFileUpload = async (category: string, file?: File) => {
        if (!settings || !file) return;
        try {
            const result = await guildManagementApi.uploadCategoryImage(category, file);
            updateCategoryImage(category, result.image_url);
            setMessage({ type: 'success', text: `Image uploaded for ${category}` });
        } catch (error) {
            console.error('Failed to upload category image:', error);
            setMessage({ type: 'error', text: `Failed upload for ${category}` });
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <RefreshCw className="w-8 h-8 animate-spin text-danger" />
            </div>
        );
    }

    if (!settings) {
        return <div className="text-center text-content-secondary">Failed to load settings</div>;
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-serif text-content-primary flex items-center gap-3">
                    <SettingsIcon className="w-8 h-8 text-danger" />
                    System Settings
                </h1>
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 bg-danger hover:bg-danger-hover disabled:bg-surface-raised disabled:text-content-muted text-content-on-primary px-6 py-2.5 rounded-md transition-colors font-medium"
                >
                    <Save className="w-4 h-4" />
                    {saving ? 'Saving...' : 'Save Changes'}
                </button>
            </div>

            {message && (
                <div className={`p-4 rounded-lg border flex items-center gap-3 ${
                    message.type === 'success'
                        ? 'bg-success/20 border-success/50 text-success'
                        : 'bg-danger/20 border-danger/50 text-danger'
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
                <EmailDiagnosticsPanel />
                {/* Tibia Validation Settings */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-content-primary mb-4">Tibia Character Validation</h2>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">Enable Validation</h3>
                                <p className="text-sm text-content-secondary">Validate character names against Tibia API during registration</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.tibia_validation_enabled}
                                    onChange={(e) => updateSetting('tibia_validation_enabled', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-danger"></div>
                            </label>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">Strict Mode</h3>
                                <p className="text-sm text-content-secondary">Block registration if Tibia API is unavailable</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.tibia_validation_strict}
                                    onChange={(e) => updateSetting('tibia_validation_strict', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-danger"></div>
                            </label>
                        </div>
                    </div>
                </div>

                {/* Discord Integration Settings */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-content-primary mb-4">Discord Integration</h2>

                    <div className="space-y-4">
                        <div>
                            <label className="block font-medium text-content-primary mb-2">Webhook URL</label>
                            <input
                                type="text"
                                value={settings.discord_webhook_url}
                                onChange={(e) => updateSetting('discord_webhook_url', e.target.value)}
                                placeholder="https://discord.com/api/webhooks/..."
                                className="w-full bg-surface-base border border-line rounded-md px-4 py-2.5 text-content-primary focus:border-danger focus:outline-none"
                            />
                            <p className="text-xs text-content-muted mt-1">
                                Get your webhook URL from Discord Server Settings → Integrations → Webhooks
                            </p>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">Auto-Post Announcements</h3>
                                <p className="text-sm text-content-secondary">Automatically post new announcements to Discord</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.discord_auto_post}
                                    onChange={(e) => updateSetting('discord_auto_post', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent"></div>
                            </label>
                        </div>
                    </div>
                </div>

                {/* Cyclopedia Category Images */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-content-primary mb-2">Cyclopedia Category Images</h2>
                    <p className="text-sm text-content-secondary mb-4">Set URL or upload local file for each creature category card.</p>

                    <div className="grid gap-4 sm:grid-cols-2">
                        {CREATURE_CATEGORY_KEYS.map((category) => (
                            <div key={category} className="rounded-lg border border-line bg-surface-base/50 p-3">
                                <div className="mb-2 text-sm font-medium text-content-primary capitalize">{category}</div>
                                <input
                                    type="text"
                                    value={settings.cyclopedia_category_images?.[category] || ''}
                                    onChange={(e) => updateCategoryImage(category, e.target.value)}
                                    placeholder="https://... or /api/v1/creatures/category-images/file/..."
                                    className="w-full bg-surface-base border border-line rounded-md px-3 py-2 text-content-primary focus:border-danger focus:outline-none"
                                />
                                <label className="mt-2 inline-flex cursor-pointer items-center rounded-md border border-line px-3 py-1.5 text-xs text-content-secondary hover:border-danger/50">
                                    Upload local image
                                    <input
                                        type="file"
                                        accept="image/*"
                                        className="hidden"
                                        onChange={(e) => handleCategoryFileUpload(category, e.target.files?.[0])}
                                    />
                                </label>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Guild Features */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-content-primary mb-4">Guild Feature Toggles</h2>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">Guild Raffles</h3>
                                <p className="text-sm text-content-secondary">Enable or disable raffle views and registration flows</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.guild_raffles_enabled}
                                    onChange={(e) => updateSetting('guild_raffles_enabled', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-danger"></div>
                            </label>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">Guild Contests</h3>
                                <p className="text-sm text-content-secondary">Enable or disable contest references in guild event flows</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings.guild_contests_enabled}
                                    onChange={(e) => updateSetting('guild_contests_enabled', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-danger"></div>
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
