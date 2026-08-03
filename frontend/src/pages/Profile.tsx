import { Bell, Castle, KeyRound, UserRound, UsersRound } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AppButton, AppTabs, EmptyState, LoadingState, Page, PageHeader } from '../components/ui';
import CharactersSection from '../components/profile/CharactersSection';
import GuildsSection from '../components/profile/GuildsSection';
import NotificationsSection from '../components/profile/NotificationsSection';
import OverviewSection from '../components/profile/OverviewSection';
import SecuritySection from '../components/profile/SecuritySection';
import { useAuth } from '../context/AuthContext';
import { useProfileIdentity } from '../hooks/useProfileIdentity';

const allowed = new Set(['overview', 'characters', 'guilds', 'security', 'notifications']);
export default function Profile() {
  const { t } = useTranslation(); const { updateUser } = useAuth(); const [params, setParams] = useSearchParams();
  const state = useProfileIdentity(); const requested = params.get('tab') || 'overview'; const tab = allowed.has(requested) ? requested : 'overview';
  const onProfile = (profile: NonNullable<typeof state.profile>) => { state.setProfile(profile); updateUser(profile); };
  if (state.loading) return <LoadingState title={t('profile.states.loading')} />;
  if (state.error || !state.profile) return <EmptyState title={t('profile.states.error')} description={t('profile.states.errorHelp')} action={<AppButton onClick={() => void state.reload()}>{t('common.retry')}</AppButton>} />;
  const tabs = [
    { key: 'overview', label: t('identity.tabs.overview'), icon: <UserRound className="size-4" /> },
    { key: 'characters', label: t('identity.tabs.characters'), icon: <UsersRound className="size-4" /> },
    { key: 'guilds', label: t('identity.tabs.guilds'), icon: <Castle className="size-4" /> },
    { key: 'security', label: t('identity.tabs.security'), icon: <KeyRound className="size-4" /> },
    { key: 'notifications', label: t('identity.tabs.notifications'), icon: <Bell className="size-4" /> },
  ];
  return <Page className="space-y-5"><PageHeader title={t('profile.title')} subtitle={t('identity.subtitle')} iconElement={<UserRound className="size-7" />} /><AppTabs items={tabs} activeKey={tab} onChange={key => setParams({ tab: key })} />
    <section role="tabpanel" aria-label={tabs.find(item => item.key === tab)?.label}>
      {tab === 'overview' && <OverviewSection profile={state.profile} onChange={onProfile} />}
      {tab === 'characters' && <CharactersSection profile={state.profile} claims={state.claims} onProfile={onProfile} onClaims={state.setClaims} />}
      {tab === 'guilds' && <GuildsSection profile={state.profile} />}
      {tab === 'security' && <SecuritySection profile={state.profile} onChange={onProfile} />}
      {tab === 'notifications' && <NotificationsSection profile={state.profile} onChange={onProfile} />}
    </section></Page>;
}
