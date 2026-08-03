import { useEffect, useState } from 'react';
import { Castle, UserRound, UsersRound } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Badge, Card, EmptyState, LoadingState, Page, PageHeader } from '../components/ui';
import { PublicProfile, profileApi } from '../services/profile';

export default function MemberProfile() {
  const { username = '' } = useParams(); const { t } = useTranslation(); const [profile, setProfile] = useState<PublicProfile>(); const [loading, setLoading] = useState(true);
  useEffect(() => { let active = true; profileApi.public(username).then(value => active && setProfile(value)).catch(() => active && setProfile(undefined)).finally(() => active && setLoading(false)); return () => { active = false; }; }, [username]);
  if (loading) return <LoadingState title={t('identity.publicLoading')} />;
  if (!profile) return <EmptyState title={t('identity.publicMissing')} description={t('identity.publicMissingHelp')} />;
  return <Page className="space-y-5"><PageHeader title={profile.display_name || profile.username} subtitle={`@${profile.username}${profile.title ? ` · ${profile.title}` : ''}`} iconElement={profile.avatar_url ? <img src={profile.avatar_url} alt="" className="size-12 rounded-full object-cover" /> : <UserRound className="size-7" />} />
    {profile.primary_character && <Card className="p-5"><h2 className="font-semibold">{t('identity.primary')}</h2><p className="mt-2 text-lg">{profile.primary_character.character_name}</p><p className="text-sm text-content-muted">{profile.primary_character.world_name || '—'} · {profile.primary_character.vocation || '—'} · {t('identity.level')} {profile.primary_character.level ?? '—'}</p></Card>}
    <section><h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><UsersRound className="size-5" />{t('identity.allCharacters')}</h2><div className="grid gap-3 md:grid-cols-2">{profile.characters.map(row => <Card key={row.id} className="p-4"><div className="flex justify-between gap-2"><strong>{row.character_name}</strong>{row.is_primary && <Badge tone="primary">{t('identity.primary')}</Badge>}</div><p className="text-sm text-content-muted">{row.world_name || '—'} · {row.guild_name || '—'} · {row.guild_rank || '—'}</p></Card>)}</div></section>
    {profile.guilds.length > 0 && <section><h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Castle className="size-5" />{t('identity.guilds')}</h2><div className="flex flex-wrap gap-2">{profile.guilds.map(row => <Badge key={`${row.guild_name}-${row.character_name}`} tone="primary">{row.guild_name} · {row.world_name || '—'}</Badge>)}</div></section>}
  </Page>;
}
