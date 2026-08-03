import { FormEvent, useState } from 'react';
import { Loader2, Save, Upload, UserRound, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { AppButton, Card, FormField, Input, Panel } from '../ui';
import { useToast } from '../../context/ToastContext';
import { ProfileIdentity, profileApi } from '../../services/profile';

export default function OverviewSection({ profile, onChange }: { profile: ProfileIdentity; onChange: (value: ProfileIdentity) => void }) {
  const { t } = useTranslation(); const toast = useToast();
  const [form, setForm] = useState({ display_name: profile.display_name || '', title: profile.title || '', email: profile.email || '' });
  const [busy, setBusy] = useState(false); const [preview, setPreview] = useState<string>();
  const save = async (event: FormEvent) => { event.preventDefault(); setBusy(true); try { onChange(await profileApi.update(form)); toast.success(t('identity.saved')); } catch { toast.error(t('identity.error')); } finally { setBusy(false); } };
  const upload = async (file?: File) => { if (!file) return; setPreview(URL.createObjectURL(file)); setBusy(true); try { onChange(await profileApi.uploadAvatar(file)); toast.success(t('identity.avatarSaved')); } catch { toast.error(t('identity.avatarError')); } finally { setBusy(false); } };
  const remove = async () => { setBusy(true); try { onChange(await profileApi.removeAvatar()); setPreview(undefined); } catch { toast.error(t('identity.avatarError')); } finally { setBusy(false); } };
  const primary = profile.character_details.find(row => row.is_primary);
  return <div className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
    <Card className="h-fit p-5 text-center"><div className="mx-auto grid size-28 place-items-center overflow-hidden rounded-full border border-line bg-surface-raised">{preview || profile.avatar_url ? <img src={preview || profile.avatar_url} alt={t('identity.avatarAlt')} className="size-full object-cover" /> : <UserRound className="size-10 text-content-muted" />}</div><h2 className="mt-4 text-xl font-semibold">{profile.display_name || profile.username}</h2><p className="text-sm text-content-muted">@{profile.username}</p><div className="mt-4 grid gap-2"><label className="app-button-secondary cursor-pointer"><Upload className="size-4" />{busy ? t('identity.working') : t('identity.uploadAvatar')}<input className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => void upload(event.target.files?.[0])} /></label>{profile.avatar_url && <AppButton variant="ghost" disabled={busy} onClick={() => void remove()}><Trash2 className="size-4" />{t('identity.removeAvatar')}</AppButton>}<p className="text-xs text-content-muted">{t('identity.avatarHelp')}</p></div></Card>
    <div className="space-y-5"><Panel className="p-5"><h2 className="font-semibold">{t('identity.account')}</h2><form onSubmit={save} className="mt-4 grid gap-4 sm:grid-cols-2"><FormField label={t('profile.fields.displayName')}><Input value={form.display_name} maxLength={100} onChange={event => setForm(v => ({ ...v, display_name: event.target.value }))} /></FormField><FormField label={t('profile.fields.title')}><Input value={form.title} maxLength={100} onChange={event => setForm(v => ({ ...v, title: event.target.value }))} /></FormField><FormField label={t('profile.fields.email')}><Input type="email" value={form.email} onChange={event => setForm(v => ({ ...v, email: event.target.value }))} /></FormField><div className="flex items-end"><AppButton type="submit" disabled={busy}>{busy ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}{t('common.save')}</AppButton></div></form></Panel>
      <Panel className="p-5"><h2 className="font-semibold">{t('identity.primary')}</h2>{primary ? <dl className="mt-3 grid gap-3 sm:grid-cols-3"><Value label={t('profile.fields.character')} value={primary.character_name} /><Value label={t('profile.fields.world')} value={primary.world_name} /><Value label={t('profile.fields.guild')} value={primary.guild_name} /><Value label={t('profile.fields.rank')} value={primary.guild_rank} /><Value label={t('profile.fields.vocation')} value={primary.vocation} /><Value label={t('identity.level')} value={primary.level} /></dl> : <p className="mt-2 text-sm text-content-muted">{t('identity.noPrimary')}</p>}</Panel></div>
  </div>;
}

function Value({ label, value }: { label: string; value?: string | number }) { return <div><dt className="text-xs text-content-muted">{label}</dt><dd className="font-medium">{value ?? '—'}</dd></div>; }
