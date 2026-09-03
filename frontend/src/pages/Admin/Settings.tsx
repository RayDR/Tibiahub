import { useState, useEffect } from 'react';
import { guildManagementApi } from '../../services/guildManagement';
import { useTranslation } from 'react-i18next';
import { Settings as SettingsIcon, Save } from 'lucide-react';
import EmailDiagnosticsPanel from '../../components/admin/EmailDiagnosticsPanel';
import { WorkspaceContentHeader } from '../../components/workspace/WorkspacePrimitives';
import { Alert, ErrorState, FormField, Input, LoadingState } from '../../components/ui';
import {
    CREATURE_CATEGORIES,
    normalizeCategoryKey,
} from '../../config/creatureCategories';

interface SystemSettings {
    tibia_validation_enabled: boolean;
    tibia_validation_strict: boolean;
    discord_webhook_url: string;
    discord_auto_post: boolean;
    guild_raffles_enabled: boolean;
    guild_contests_enabled: boolean;
    cyclopedia_category_images: Record<string, string>;
}

const CREATURE_CATEGORY_KEYS = CREATURE_CATEGORIES
    .filter((category) => category !== '')
    .map((category) => ({
        category,
        key: normalizeCategoryKey(category),
    }));

export default function AdminSettings() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<SystemSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [loadError, setLoadError] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        setLoading(true);
        setLoadError(false);
        try {
            const data = await guildManagementApi.getSettings();
            setSettings(data);
        } catch (error) {
            console.error('Failed to load settings:', error);
            setLoadError(true);
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
            setMessage({ type: 'success', text: t('adminSettings.messages.saved') });
        } catch (error) {
            console.error('Failed to save settings:', error);
            setMessage({ type: 'error', text: t('adminSettings.messages.saveError') });
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
            setMessage({ type: 'success', text: t('adminSettings.messages.imageUploaded', { category }) });
        } catch (error) {
            console.error('Failed to upload category image:', error);
            setMessage({ type: 'error', text: t('adminSettings.messages.imageError', { category }) });
        }
    };

    if (loading) {
        return <LoadingState title={t('adminSettings.states.loading')} />;
    }

    if (loadError || !settings) {
        return <ErrorState title={t('adminSettings.states.error')} description={t('adminSettings.states.errorHelp')} action={<button type="button" onClick={() => void loadSettings()} className="app-button-secondary">{t('common.retry')}</button>} />;
    }

    return (
        <div className="workspace-page">
            <WorkspaceContentHeader
                title={t('adminSettings.title')}
                icon={<SettingsIcon />}
                action={<button
                    onClick={handleSave}
                    disabled={saving}
                    className="app-button-primary"
                >
                    <Save className="w-4 h-4" />
                    {saving ? t('adminSettings.actions.saving') : t('adminSettings.actions.save')}
                </button>}
            />

            {message && (
                <Alert tone={message.type === 'success' ? 'success' : 'danger'}>{message.text}</Alert>
            )}

            <div className="space-y-6">
                <EmailDiagnosticsPanel />
                {/* Tibia Validation Settings */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-content-primary mb-4">{t('adminSettings.validation.title')}</h2>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">{t('adminSettings.validation.enabled')}</h3>
                                <p className="text-sm text-content-secondary">{t('adminSettings.validation.enabledHelp')}</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    aria-label={t('adminSettings.validation.enabledAria')}
                                    checked={settings.tibia_validation_enabled}
                                    onChange={(e) => updateSetting('tibia_validation_enabled', e.target.checked)}
                                    disabled={saving}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-danger"></div>
                            </label>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">{t('adminSettings.validation.strict')}</h3>
                                <p className="text-sm text-content-secondary">{t('adminSettings.validation.strictHelp')}</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    aria-label={t('adminSettings.validation.strictAria')}
                                    checked={settings.tibia_validation_strict}
                                    onChange={(e) => updateSetting('tibia_validation_strict', e.target.checked)}
                                    disabled={saving}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-danger"></div>
                            </label>
                        </div>
                    </div>
                </div>

                {/* Discord Integration Settings */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-content-primary mb-4">{t('adminSettings.discord.title')}</h2>

                    <div className="space-y-4">
                        <FormField label={t('adminSettings.discord.webhook')} helpText={t('adminSettings.discord.webhookHelp')}>
                            <Input
                                type="text"
                                value={settings.discord_webhook_url}
                                onChange={(e) => updateSetting('discord_webhook_url', e.target.value)}
                                placeholder="https://discord.com/api/webhooks/..."
                                disabled={saving}
                            />
                        </FormField>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">{t('adminSettings.discord.autoPost')}</h3>
                                <p className="text-sm text-content-secondary">{t('adminSettings.discord.autoPostHelp')}</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    aria-label={t('adminSettings.discord.autoPostAria')}
                                    checked={settings.discord_auto_post}
                                    onChange={(e) => updateSetting('discord_auto_post', e.target.checked)}
                                    disabled={saving}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent"></div>
                            </label>
                        </div>
                    </div>
                </div>

                {/* Cyclopedia Category Images */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-content-primary mb-2">{t('adminSettings.images.title')}</h2>
                    <p className="text-sm text-content-secondary mb-4">{t('adminSettings.images.help')}</p>

                    <div className="grid gap-4 sm:grid-cols-2">
                        {CREATURE_CATEGORY_KEYS.map(({ category, key }) => (
                            <div key={key} className="rounded-lg border border-line bg-surface-base/50 p-3">
                                <FormField label={category}>
                                <Input
                                    type="text"
                                    value={settings.cyclopedia_category_images?.[key] || ''}
                                    onChange={(e) => updateCategoryImage(key, e.target.value)}
                                    placeholder="https://... or /api/v1/creatures/category-images/file/..."
                                    disabled={saving}
                                />
                                </FormField>
                                <label className="mt-2 inline-flex cursor-pointer items-center rounded-md border border-line px-3 py-1.5 text-xs text-content-secondary hover:border-danger/50">
                                    {t('adminSettings.images.upload')}
                                    <input
                                        type="file"
                                        accept="image/*"
                                        className="hidden"
                                        disabled={saving}
                                        onChange={(e) => handleCategoryFileUpload(key, e.target.files?.[0])}
                                    />
                                </label>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Guild Features */}
                <div className="bg-surface-base/50 border border-line rounded-lg p-6">
                    <h2 className="text-xl font-semibold text-content-primary mb-4">{t('adminSettings.features.title')}</h2>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">{t('adminSettings.features.raffles')}</h3>
                                <p className="text-sm text-content-secondary">{t('adminSettings.features.rafflesHelp')}</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    aria-label={t('adminSettings.features.rafflesAria')}
                                    checked={settings.guild_raffles_enabled}
                                    onChange={(e) => updateSetting('guild_raffles_enabled', e.target.checked)}
                                    disabled={saving}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-surface-raised peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-danger rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-line after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-surface-inverse after:border-line after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-danger"></div>
                            </label>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-content-primary">{t('adminSettings.features.contests')}</h3>
                                <p className="text-sm text-content-secondary">{t('adminSettings.features.contestsHelp')}</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    aria-label={t('adminSettings.features.contestsAria')}
                                    checked={settings.guild_contests_enabled}
                                    onChange={(e) => updateSetting('guild_contests_enabled', e.target.checked)}
                                    disabled={saving}
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
