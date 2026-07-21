import { Routes, Route, useLocation, useNavigate, Navigate } from 'react-router-dom';
import Navigation from './components/Navigation';
import HomePage from './pages/HomePage';
import CreaturesPage from './pages/CreaturesPage';
import CreatureDetailPage from './pages/CreatureDetailPage';
import QuestDetailPage from './pages/QuestDetailPage';
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
import { useEffect } from 'react';
import { useState } from 'react';

import { AuthProvider } from './context/AuthContext';
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
import Raffle from './pages/guild/Raffle';
import AutomaticRaffleOperations from './pages/guild/AutomaticRaffleOperations';
import NotificationsPage from './pages/guild/Notifications';
import RafflePublicPage from './pages/RafflePublicPage';
import PublicRafflePage from './pages/PublicRafflePage';
import NotFound from './pages/NotFound';
import { systemApi } from './services/api';

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [latestDataVersion, setLatestDataVersion] = useState<string>('Latest data version unavailable');

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
      <ToastProvider>
        <div className="min-h-screen text-[color:var(--color-text)] font-sans pt-20" style={{ backgroundColor: 'var(--color-bg)' }}>
          <Navigation />

          <div className="container mx-auto px-4">
            <Routes location={location} key={location.pathname}>
              <Route path="/" element={<HomePage />} />
              <Route path="/cyclopedia" element={<CreaturesPage />} />
              <Route path="/bestiary" element={<Navigate to="/cyclopedia?tab=creatures" replace />} />
              <Route path="/quests" element={<Navigate to="/cyclopedia?tab=quests" replace />} />
              <Route path="/missions" element={<Navigate to="/cyclopedia?tab=quests" replace />} />
              <Route path="/creatures/:slug" element={<CreatureDetailPage />} />
              <Route path="/quests/:questId" element={<QuestDetailPage />} />
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
                <Route path="recruitment" element={<Navigate to="/guild/events?type=contest" replace />} />
                <Route path="hunts" element={<HuntCatalog />} />
                <Route path="raffle" element={<Raffle />} />
                <Route path="automatic-raffles" element={<AutomaticRaffleOperations />} />
                <Route path="notifications" element={<NotificationsPage />} />
              </Route>

              {/* Admin Routes */}
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<AdminRedirect />} />
                <Route path="overview" element={<Overview />} />
                <Route path="management" element={<GuildManagementDashboard />} />
                <Route path="guild-view" element={<GuildView />} />
                <Route path="bestiary" element={<BestiaryManagement />} />
                <Route path="data-tools" element={<DataTools />} />
                <Route path="settings" element={<AdminSettings />} />
                {/* Legacy redirects */}
                <Route path="api-monitor" element={<Navigate to="/admin/data-tools" replace />} />
                <Route path="database-sync" element={<Navigate to="/admin/data-tools" replace />} />
                <Route path="sync" element={<Navigate to="/admin/data-tools" replace />} />
              </Route>

              {/* Catch-All */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </div>

          {/* Footer */}
          <footer className="mt-24 text-center border-t border-slate-800 pt-8 pb-8">
            <div className="inline-block">
              <p className="text-slate-400 text-sm">Tibia Cyclopedia - Fan-made project ({latestDataVersion})</p>
              <p className="mt-2 text-slate-600 text-xs">
                Tibia is a registered trademark of CipSoft GmbH
              </p>
              <p className="mt-2 text-slate-500 text-xs">
                Data sourced from <a href="https://tibia.fandom.com" target="_blank" rel="noopener noreferrer" className="text-amber-500 hover:text-amber-400 transition-colors">TibiaWiki</a>
              </p>
            </div>
          </footer>
        </div>
      </ToastProvider>
    </AuthProvider>
  );
}



export default App;
