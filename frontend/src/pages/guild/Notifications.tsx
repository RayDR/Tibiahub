import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { InternalNotification, notificationApi } from '../../services/notifications';

export default function NotificationsPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<InternalNotification[]>([]);
  useEffect(() => { void notificationApi.list().then(setItems); }, []);
  const markAll = async () => { await notificationApi.markAllRead(); setItems((rows) => rows.map((row) => ({ ...row, is_read: true }))); };
  return <div className="space-y-4">
    <div className="flex items-center justify-between"><h1 className="text-2xl font-bold">{t('notifications.title')}</h1><button onClick={markAll} className="rounded-lg border border-slate-700 px-3 py-2">{t('notifications.markAll')}</button></div>
    {items.length === 0 && <p className="text-slate-400">{t('notifications.empty')}</p>}
    {items.map((item) => <button key={item.id} onClick={async () => { await notificationApi.markRead(item.id); setItems((rows) => rows.map((row) => row.id === item.id ? { ...row, is_read: true } : row)); }} className={`block w-full rounded-xl border p-4 text-left ${item.is_read ? 'border-slate-800 opacity-70' : 'border-amber-500/40'}`}>
      <strong>{t(item.title_key, item.interpolation)}</strong><p className="text-sm text-slate-400">{t(item.message_key, item.interpolation)}</p>
    </button>)}
  </div>;
}
