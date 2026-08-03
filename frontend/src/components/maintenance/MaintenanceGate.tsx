import { ReactNode, useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { maintenanceModeApi, MaintenanceStatus } from '../../services/maintenanceMode';
import MaintenanceScreen from './MaintenanceScreen';

const OPEN_PATHS = ['/login', '/reset-password', '/verify-email'];

export default function MaintenanceGate({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [status, setStatus] = useState<MaintenanceStatus | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try { setStatus(await maintenanceModeApi.status()); } catch { /* Preserve the last safe state during a transient status failure. */ }
    finally { setRefreshing(false); }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    if (!status?.active) return;
    const shortcut = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'a') {
        event.preventDefault();
        navigate('/login?maintenance=1');
      }
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, [navigate, status?.active]);

  const pathIsOpen = OPEN_PATHS.some(path => location.pathname.startsWith(path));
  if (!authLoading && status?.active && !user?.is_superuser && !pathIsOpen) {
    return <MaintenanceScreen status={status} refresh={() => void refresh()} refreshing={refreshing} />;
  }
  return <>{children}</>;
}
