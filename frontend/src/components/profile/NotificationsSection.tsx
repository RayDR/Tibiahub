import { useState } from 'react';
import { Bell, Mail } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { AppButton, Panel } from '../ui';
import { useToast } from '../../context/ToastContext';
import { ProfileIdentity, profileApi } from '../../services/profile';

export default function NotificationsSection({ profile, onChange }: { profile: ProfileIdentity; onChange: (value: ProfileIdentity) => void }) {
  const { t } = useTranslation(); const toast = useToast(); const [inApp, setInApp] = useState(profile.in_app_notifications_enabled); const [email, setEmail] = useState(profile.email_notifications_enabled); const [busy, setBusy] = useState(false);
  const save = async () => { setBusy(true); try { onChange(await profileApi.preferences(inApp, email)); toast.success(t('identity.saved')); } catch { toast.error(t('identity.error')); } finally { setBusy(false); } };
  return <Panel className="space-y-4 p-5"><h2 className="font-semibold">{t('identity.notificationPreferences')}</h2><label className="flex min-h-12 items-center justify-between gap-4 rounded-lg border border-line p-3"><span className="flex items-center gap-3"><Bell className="size-5 text-primary" /><span><strong className="block">{t('identity.inApp')}</strong><small className="text-content-muted">{t('identity.inAppHelp')}</small></span></span><input type="checkbox" checked={inApp} onChange={event => setInApp(event.target.checked)} /></label><label className="flex min-h-12 items-center justify-between gap-4 rounded-lg border border-line p-3"><span className="flex items-center gap-3"><Mail className="size-5 text-primary" /><span><strong className="block">{t('identity.emailNotifications')}</strong><small className="text-content-muted">{t('identity.emailNotificationsHelp')}</small></span></span><input type="checkbox" checked={email} onChange={event => setEmail(event.target.checked)} /></label><p className="text-xs text-content-muted">{t('identity.securityEmailHelp')}</p><AppButton disabled={busy} onClick={() => void save()}>{t('common.save')}</AppButton></Panel>;
}
