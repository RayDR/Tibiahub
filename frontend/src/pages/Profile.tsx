import { FormEvent, useEffect, useState } from 'react';
import { BadgeInfo, Calendar, Edit2, Link2, Loader2, Lock, Mail, Save, Shield, Tag, User, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Card, EmptyState, FormField, Input, LoadingState, Page, PageHeader, Panel } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import api from '../services/api';

interface ProfileData {
  username: string; display_name?: string; title?: string; email: string; avatar_url?: string; tibia_character_name: string;
  guild_rank?: string; guild_name?: string; world_name?: string; residence?: string; vocation?: string; level?: number;
  achievement_points?: number; tibia_status?: string; tibia_last_error?: string; is_active: boolean; join_date?: string; created_at: string;
}

const emptyForm = { display_name: '', title: '', email: '', avatar_url: '', tibia_character_name: '', current_password: '', new_password: '', confirm_password: '' };

export default function Profile() {
  const { t, i18n } = useTranslation();
  const { updateUser } = useAuth();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [profileData, setProfileData] = useState<ProfileData | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [formData, setFormData] = useState(emptyForm);

  const populate = (data: ProfileData) => setFormData({ ...emptyForm, display_name: data.display_name || '', title: data.title || '', email: data.email || '', avatar_url: data.avatar_url || '', tibia_character_name: data.tibia_character_name || '' });
  const loadProfile = async () => {
    setLoading(true); setLoadError(false);
    try { const response = await api.get<ProfileData>('/profile/me'); setProfileData(response.data); populate(response.data); }
    catch { setLoadError(true); toast.error(t('profile.messages.loadError')); }
    finally { setLoading(false); }
  };
  useEffect(() => { void loadProfile(); }, []);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (formData.new_password && formData.new_password !== formData.confirm_password) { toast.error(t('profile.messages.passwordMismatch')); return; }
    if (formData.new_password && !formData.current_password) { toast.error(t('profile.messages.currentRequired')); return; }
    setSaving(true);
    try {
      const payload: Record<string, string> = { display_name: formData.display_name, title: formData.title, email: formData.email, avatar_url: formData.avatar_url };
      if (formData.new_password) { payload.current_password = formData.current_password; payload.new_password = formData.new_password; }
      const response = await api.put<ProfileData>('/profile/me', payload);
      setProfileData(response.data); populate(response.data); setEditing(false); updateUser?.(response.data); toast.success(t('profile.messages.saved'));
    } catch { toast.error(t('profile.messages.saveError')); }
    finally { setSaving(false); }
  };
  const cancel = () => { setEditing(false); if (profileData) populate(profileData); };

  if (loading) return <LoadingState className="my-8 rounded-xl border border-line" title={t('profile.states.loading')} />;
  if (loadError || !profileData) return <div className="py-8"><EmptyState title={t('profile.states.error')} description={t('profile.states.errorHelp')} action={<AppButton onClick={() => void loadProfile()}>{t('common.retry')}</AppButton>} /></div>;
  const missing = t('profile.values.notSet');
  const joined = new Date(profileData.join_date || profileData.created_at).toLocaleDateString(i18n.language);

  return <Page className="space-y-5">
    <PageHeader title={t('profile.title')} subtitle={t('profile.subtitle')} iconElement={<User className="size-7" />} primaryAction={!editing ? <AppButton onClick={() => setEditing(true)}><Edit2 className="size-4" />{t('profile.actions.edit')}</AppButton> : undefined} />
    <div className="grid min-w-0 gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="space-y-4">
        <Card className="p-5 text-center"><div className="mx-auto grid size-24 place-items-center overflow-hidden rounded-full border border-line bg-surface-raised">{profileData.avatar_url ? <img src={profileData.avatar_url} alt={t('profile.fields.avatarAlt')} className="size-full object-cover" onError={event => { (event.currentTarget as HTMLImageElement).style.display = 'none'; }} /> : <User className="size-10 text-content-muted" />}</div><h2 className="mt-4 text-xl font-semibold">{profileData.display_name || profileData.username}</h2><p className="text-sm text-content-muted">{profileData.title || t('profile.values.noTitle')}</p><Badge className="mt-3" tone={profileData.is_active ? 'success' : 'neutral'}>{t(profileData.is_active ? 'common.active' : 'common.inactive')}</Badge></Card>
        <Panel className="p-4"><dl className="space-y-3 text-sm"><ProfileValue label={t('profile.fields.character')} value={profileData.tibia_character_name || missing} /><ProfileValue label={t('profile.fields.vocation')} value={profileData.vocation ? t('profile.values.vocationLevel', { vocation: profileData.vocation, level: profileData.level ?? missing }) : missing} /><ProfileValue label={t('profile.fields.guild')} value={profileData.guild_name || missing} /><ProfileValue label={t('profile.fields.rank')} value={profileData.guild_rank || missing} /><ProfileValue label={t('profile.fields.world')} value={profileData.world_name || missing} /></dl></Panel>
      </aside>

      <form onSubmit={save} className="min-w-0 space-y-5">
        <Panel className="overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4 sm:p-5"><div><h2 className="font-semibold">{t('profile.account.title')}</h2><p className="text-sm text-content-muted">{editing ? t('profile.account.editing') : t('profile.account.readOnly')}</p></div>{editing ? <div className="flex gap-2"><AppButton type="button" variant="ghost" onClick={cancel} disabled={saving}><X className="size-4" />{t('profile.actions.cancel')}</AppButton><AppButton type="submit" disabled={saving}>{saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}{t('profile.actions.save')}</AppButton></div> : null}</div>
          <div className="grid gap-5 p-4 sm:p-5 md:grid-cols-2">
            <EditableField editing={editing} label={t('profile.fields.displayName')} icon={<Tag />} value={formData.display_name} display={profileData.display_name || missing} placeholder={t('profile.placeholders.displayName')} onChange={value => setFormData(current => ({ ...current, display_name: value }))} />
            <EditableField editing={editing} label={t('profile.fields.title')} icon={<BadgeInfo />} value={formData.title} display={profileData.title || missing} placeholder={t('profile.placeholders.title')} onChange={value => setFormData(current => ({ ...current, title: value }))} />
            <EditableField editing={editing} label={t('profile.fields.email')} icon={<Mail />} type="email" value={formData.email} display={profileData.email || missing} placeholder={t('profile.placeholders.email')} onChange={value => setFormData(current => ({ ...current, email: value }))} />
            <EditableField editing={editing} label={t('profile.fields.avatar')} icon={<Link2 />} type="url" value={formData.avatar_url} display={profileData.avatar_url || missing} placeholder={t('profile.placeholders.avatar')} onChange={value => setFormData(current => ({ ...current, avatar_url: value }))} />
            <ReadOnlyField label={t('profile.fields.username')} value={profileData.username} help={t('profile.fields.usernameHelp')} />
            <ReadOnlyField label={t('profile.fields.character')} value={profileData.tibia_character_name || missing} help={t('profile.fields.characterHelp')} />
          </div>
        </Panel>

        <Panel className="p-4 sm:p-5"><h2 className="flex items-center gap-2 font-semibold"><Shield className="size-4 text-primary" />{t('profile.tibia.title')}</h2><dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3"><ProfileValue label={t('profile.fields.residence')} value={profileData.residence || missing} /><ProfileValue label={t('profile.fields.status')} value={profileData.tibia_status || t('profile.values.unknown')} /><ProfileValue label={t('profile.fields.achievementPoints')} value={profileData.achievement_points?.toLocaleString() || missing} /><ProfileValue label={t('profile.fields.memberSince')} value={joined} icon={<Calendar />} /></dl>{profileData.tibia_last_error ? <p className="mt-4 rounded-lg bg-danger-subtle p-3 text-sm text-danger">{profileData.tibia_last_error}</p> : null}</Panel>

        {editing ? <Panel className="p-4 sm:p-5"><h2 className="flex items-center gap-2 font-semibold"><Lock className="size-4 text-primary" />{t('profile.password.title')}</h2><p className="mt-1 text-sm text-content-muted">{t('profile.password.help')}</p><div className="mt-4 grid gap-4 md:grid-cols-3"><FormField label={t('profile.password.current')}><Input type="password" autoComplete="current-password" value={formData.current_password} onChange={event => setFormData(current => ({ ...current, current_password: event.target.value }))} /></FormField><FormField label={t('profile.password.new')}><Input type="password" autoComplete="new-password" value={formData.new_password} onChange={event => setFormData(current => ({ ...current, new_password: event.target.value }))} /></FormField><FormField label={t('profile.password.confirm')}><Input type="password" autoComplete="new-password" value={formData.confirm_password} onChange={event => setFormData(current => ({ ...current, confirm_password: event.target.value }))} /></FormField></div></Panel> : null}
      </form>
    </div>
  </Page>;
}

function ProfileValue({ label, value, icon }: { label: string; value: string | number; icon?: React.ReactNode }) { return <div className="min-w-0"><dt className="flex items-center gap-1 text-xs uppercase tracking-wide text-content-muted">{icon}{label}</dt><dd className="mt-1 break-words font-medium text-content-primary">{value}</dd></div>; }
function ReadOnlyField({ label, value, help }: { label: string; value: string; help: string }) { return <FormField label={label} helpText={help}><div className="min-h-11 rounded-md border border-line bg-disabled px-3 py-2 text-content-secondary">{value}</div></FormField>; }
function EditableField({ editing, label, icon, type = 'text', value, display, placeholder, onChange }: { editing: boolean; label: string; icon: React.ReactNode; type?: string; value: string; display: string; placeholder: string; onChange: (value: string) => void }) { return <FormField label={<span className="flex items-center gap-1">{icon}<span>{label}</span></span>}>{editing ? <Input type={type} value={value} placeholder={placeholder} onChange={event => onChange(event.target.value)} /> : <div className="min-h-11 break-words rounded-md border border-line bg-surface-raised px-3 py-2 text-content-primary">{display}</div>}</FormField>; }
