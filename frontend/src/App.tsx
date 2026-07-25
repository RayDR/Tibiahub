import { Routes, Route, useLocation, useNavigate, Navigate } from 'react-router-dom';
import Navigation from './components/Navigation';
import HomePage from './pages/HomePage';
import CreaturesPage from './pages/CreaturesPage';
import CreatureDetailPage from './pages/CreatureDetailPage';
import QuestDetailPage from './pages/QuestDetailPage';
import NpcDetailPage from './pages/NpcDetailPage';
import LocationDetailPage from './pages/LocationDetailPage';
import HuntRecommendationsPage from './pages/HuntRecommendationsPage';
import QuestViewerPage from './pages/QuestViewerPage';
import GuildManagementDashboard from './pages/Admin/GuildManagementDashboard';
import BestiaryManagement from './pages/Admin/BestiaryManagement';
import AdminRedirect from './pages/Admin/AdminRedirect';
import AdminSettings from './pages/Admin/Settings';
import DataTools from './pages/Admin/DataTools';
import Overview from './pages/Admin/Overview';
import GuildView from './pages/Admin/GuildView';
import Profile from './pages/Profile';
import PasswordReset from './pages/PasswordReset';
import { lazy, Suspense, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { AuthProvider } from './context/AuthContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { ToastProvider } from './context/ToastContext';
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import GuildLayout from './layouts/GuildLayout';
import AdminLayout from './layouts/AdminLayout';
import GuildDashboard from './pages/guild/Dashboard';
import GuildMembersPage from './pages/guild/Members';
import Announcements from './pages/guild/Announcements';
import Events from './pages/guild/Events';
import HuntCatalog from './pages/guild/HuntCatalog';
import RafflesWorkspace from './pages/guild/RafflesWorkspace';
import GuildDirectory from './pages/Admin/GuildDirectory';
import AdminUsers from './pages/Admin/Users';
import AdminGuildWorkspace from './pages/Admin/AdminGuildWorkspace';
import AdminGuildRaffles from './pages/Admin/AdminGuildRaffles';
import GlobalActivities from './pages/Admin/GlobalActivities';
import NotificationsPage from './pages/guild/Notifications';
import RafflePublicPage from './pages/RafflePublicPage';
import PublicRafflePage from './pages/PublicRafflePage';
import NotFound from './pages/NotFound';
import { systemApi } from './services/api';
import { Container } from './components/ui';
import ThemePlayground from './pages/Admin/ThemePlayground';

const Leadership = lazy(() => import('./pages/guild/Leadership'));
const LeadershipRecruitment = lazy(() => import('./pages/guild/LeadershipRecruitment'));
const LeadershipApplicationDetail = lazy(() => import('./pages/guild/LeadershipApplicationDetail'));
const AdminGuildLeadership = lazy(() => import('./pages/Admin/AdminGuildLeadership'));

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [latestDataVersion, setLatestDataVersion] = useState<string>('');
  const { t } = useTranslation();
  const leadershipFallback = <div role="status" className="p-8 text-center text-content-secondary">{t('leadership.loading')}</div>;

  // Keyboard shortcut listener for Ctrl+Alt+G (Guild) and Ctrl+Alt+A (Admin)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.altKey && (e.key === 'g' || e.key === 'G')) {
        e.preventDefault();
        navigate('/guild');
      }
      if (e.ctrlKey && e.altKey && (e.key === 'a' || e.key === 'A')) {
        e.preventDefault();
        navigate('/admin');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigate]);

  useEffect(() => {
    const controller = new AbortController();
    void systemApi.getHealth(controller.signal)
      .then((payload) => {
        const version = payload?.external_sync?.latest_data_version;
        if (version) {
          setLatestDataVersion(version);
        }
      })
      .catch(() => {
        // Keep graceful fallback text when health endpoint is unreachable.
      });
    return () => controller.abort();
  }, []);

  return (
    <AuthProvider>
      <WorkspaceProvider>
      <ToastProvider>
        <div className="min-h-screen bg-surface-base text-content-primary font-sans pt-20">
          <Navigation />

          <Container className="container px-4">
            <Routes location={location} key={location.pathname}>
              <Route path="/" element={<HomePage />} />
              <Route path="/cyclopedia" element={<CreaturesPage />} />
              <Route path="/bestiary" element={<Navigate to="/cyclopedia?tab=creatures" replace />} />
              <Route path="/quests" element={<Navigate to="/cyclopedia?tab=quests" replace />} />
              <Route path="/missions" element={<Navigate to="/cyclopedia?tab=quests" replace />} />
              <Route path="/creatures/:slug" element={<CreatureDetailPage />} />
              <Route path="/quests/:questId" element={<QuestDetailPage />} />
              <Route path="/npcs/:identifier" element={<NpcDetailPage />} />
              <Route path="/locations/:identifier" element={<LocationDetailPage />} />
              <Route path="/planner" element={<HuntRecommendationsPage />} />
              <Route path="/recommendations" element={<Navigate to="/planner" replace />} />
              <Route path="/hunt" element={<Navigate to="/planner" replace />} />
              <Route path="/requests" element={<QuestViewerPage />} />

              {/* Public Event Route */}
              <Route path="/public/event/:uuid" element={<PublicRafflePage />} />
              <Route path="/raffle/:id" element={<RafflePublicPage />} />
              <Route path="/raffles/:publicCode" element={<RafflePublicPage />} />
              <Route path="/contests/:publicCode" element={<PublicRafflePage />} />

              {/* Auth Routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/reset-password" element={<PasswordReset />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/settings" element={<Navigate to="/profile" replace />} />

              {/* Guild Routes */}
              <Route path="/guild" element={<GuildLayout />}>
                <Route index element={<Navigate to="dashboard" replace />} />
                <Route path="dashboard" element={<GuildDashboard />} />
                <Route path="members" element={<GuildMembersPage />} />
                <Route path="announcements" element={<Announcements />} />
                <Route path="events" element={<Events />} />
                <Route path="leadership" element={<Suspense fallback={leadershipFallback}><Leadership /></Suspense>} />
                <Route path="leadership/recruitment" element={<Suspense fallback={leadershipFallback}><LeadershipRecruitment /></Suspense>} />
                <Route path="leadership/recruitment/applications/:applicationId" element={<Suspense fallback={leadershipFallback}><LeadershipApplicationDetail /></Suspense>} />
                <Route path="recruitment" element={<Navigate to="/guild/leadership/recruitment" replace />} />
                <Route path="hunts" element={<HuntCatalog />} />
                <Route path="raffles" element={<RafflesWorkspace />} />
                <Route path="raffle" element={<Navigate to="/guild/raffles?section=history" replace />} />
                <Route path="automatic-raffles" element={<Navigate to="/guild/raffles" replace />} />
                <Route path="notifications" element={<NotificationsPage />} />
              </Route>

              {/* Admin Routes */}
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<AdminRedirect />} />
                <Route path="overview" element={<Overview />} />
                <Route path="guilds" element={<GuildDirectory />} />
                <Route path="users" element={<AdminUsers />} />
                <Route path="guilds/:guildKey" element={<AdminGuildWorkspace />} />
                <Route path="guilds/:guildKey/raffles" element={<AdminGuildRaffles />} />
                <Route path="guilds/:guildKey/leadership" element={<Suspense fallback={leadershipFallback}><AdminGuildLeadership /></Suspense>} />
                <Route path="guilds/:guildKey/leadership/recruitment" element={<Suspense fallback={leadershipFallback}><AdminGuildLeadership recruitment /></Suspense>} />
                <Route path="guilds/:guildKey/leadership/recruitment/applications/:applicationId" element={<Suspense fallback={leadershipFallback}><LeadershipApplicationDetail admin /></Suspense>} />
                <Route path="activities" element={<GlobalActivities />} />
                <Route path="management" element={<GuildManagementDashboard />} />
                <Route path="guild-view" element={<GuildView />} />
                <Route path="bestiary" element={<BestiaryManagement />} />
                <Route path="data-tools" element={<DataTools />} />
                <Route path="theme-playground" element={<ThemePlayground />} />
                <Route path="settings" element={<AdminSettings />} />
                {/* Legacy redirects */}
                <Route path="api-monitor" element={<Navigate to="/admin/data-tools" replace />} />
                <Route path="database-sync" element={<Navigate to="/admin/data-tools" replace />} />
                <Route path="sync" element={<Navigate to="/admin/data-tools" replace />} />
              </Route>

              {/* Catch-All */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Container>

          {/* Footer */}
          <footer className="mt-24 text-center border-t border-line pt-8 pb-8">
            <div className="inline-block">
              <p className="text-content-secondary text-sm">{t('footer.project', { version: latestDataVersion || t('footer.unavailable') })}</p>
              <p className="mt-2 text-content-muted text-xs">
                {t('footer.trademark')}
              </p>
              <p className="mt-2 text-content-muted text-xs">
                {t('footer.dataSource')} <a href="https://tibia.fandom.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary transition-colors">TibiaWiki</a>
              </p>
            </div>
          </footer>
        </div>
      </ToastProvider>
      </WorkspaceProvider>
    </AuthProvider>
  );
}



export default App;
