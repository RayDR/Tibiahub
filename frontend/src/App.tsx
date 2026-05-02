import { Routes, Route, useLocation, useNavigate, Navigate } from 'react-router-dom';
import Navigation from './components/Navigation';
import HomePage from './pages/HomePage';
import CreaturesPage from './pages/CreaturesPage';
import CreatureDetailPage from './pages/CreatureDetailPage';
import HuntRecommendationsPage from './pages/HuntRecommendationsPage';
import QuestViewerPage from './pages/QuestViewerPage';
import GuildManagementDashboard from './pages/Admin/GuildManagementDashboard';
import AdminRedirect from './pages/Admin/AdminRedirect';
import AdminSettings from './pages/Admin/Settings';
import APIMonitor from './pages/Admin/APIMonitor';
import DatabaseSync from './pages/Admin/DatabaseSync';
import DataSyncPanel from './pages/DataSyncPanel';
import Profile from './pages/Profile';
import PasswordReset from './pages/PasswordReset';
import { useEffect } from 'react';

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
import Recruitment from './pages/guild/Recruitment';
import HuntCatalog from './pages/guild/HuntCatalog';
import Raffle from './pages/guild/Raffle';
import RafflePublicPage from './pages/RafflePublicPage';
import PublicRafflePage from './pages/PublicRafflePage';
import NotFound from './pages/NotFound';

function App() {
  const location = useLocation();
  const navigate = useNavigate();

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

  return (
    <AuthProvider>
      <ToastProvider>
        <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-amber-500/30 pt-20">
          <Navigation />

          <div className="container mx-auto px-4">
            <Routes location={location} key={location.pathname}>
              <Route path="/" element={<HomePage />} />
              <Route path="/bestiary" element={<CreaturesPage />} />
              <Route path="/creatures/:slug" element={<CreatureDetailPage />} />
              <Route path="/recommendations" element={<HuntRecommendationsPage />} />
              <Route path="/requests" element={<QuestViewerPage />} />

              {/* Public Event Route */}
              <Route path="/public/event/:uuid" element={<PublicRafflePage />} />
              <Route path="/raffle/:id" element={<RafflePublicPage />} />

              {/* Auth Routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/reset-password" element={<PasswordReset />} />
              <Route path="/profile" element={<Profile />} />

              {/* Guild Routes */}
              <Route path="/guild" element={<GuildLayout />}>
                <Route index element={<Navigate to="dashboard" replace />} />
                <Route path="dashboard" element={<GuildDashboard />} />
                <Route path="members" element={<GuildMembersPage />} />
                <Route path="announcements" element={<Announcements />} />
                <Route path="events" element={<Events />} />
                <Route path="recruitment" element={<Recruitment />} />
                <Route path="hunts" element={<HuntCatalog />} />
                <Route path="raffle" element={<Raffle />} />
              </Route>

              {/* Admin Routes */}
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<AdminRedirect />} />
                <Route path="management" element={<GuildManagementDashboard />} />
                <Route path="api-monitor" element={<APIMonitor />} />
                <Route path="database-sync" element={<DatabaseSync />} />
                <Route path="sync" element={<DataSyncPanel />} />
                <Route path="settings" element={<AdminSettings />} />
              </Route>

              {/* Catch-All */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </div>

          {/* Footer */}
          <footer className="mt-24 text-center border-t border-slate-800 pt-8 pb-8">
            <div className="inline-block">
              <p className="text-slate-400 text-sm">Tibia Bestiary - Fan-made project (Winter Update 2025)</p>
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
