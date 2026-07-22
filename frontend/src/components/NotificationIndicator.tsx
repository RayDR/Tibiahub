import { Bell } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { notificationApi } from '../services/notifications';

export default function NotificationIndicator() {
  const { t } = useTranslation();
  const [count, setCount] = useState(0);
  useEffect(() => {
    let active = true;
    void notificationApi.unreadCount().then((value) => active && setCount(value)).catch(() => undefined);
    return () => { active = false; };
  }, []);
  return (
    <Link to="/guild/notifications" aria-label={t('notifications.indicator', { count })} className="app-nav-link relative rounded-xl p-2">
      <Bell size={18} />
      {count > 0 && <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-amber-500 px-1 text-center text-[10px] font-bold text-slate-950">{Math.min(count, 99)}</span>}
    </Link>
  );
}
