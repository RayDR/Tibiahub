import { Bell, BellRing, CheckCheck, Clock3 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { AppButton, Badge, Card, EmptyState, LoadingState, PageHeader } from '../../components/ui';
import { InternalNotification, notificationApi } from '../../services/notifications';

export default function NotificationsPage() {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<InternalNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const unread = useMemo(() => items.filter(item => !item.is_read).length, [items]);
  const load = async () => { setLoading(true); setError(false); try { const rows = await notificationApi.list(0, 20); setItems(rows); setHasMore(rows.length === 20); } catch { setError(true); } finally { setLoading(false); } };
  const loadMore = async () => { setLoadingMore(true); setError(false); try { const rows = await notificationApi.list(items.length, 20); setItems((current) => [...current, ...rows]); setHasMore(rows.length === 20); } catch { setError(true); } finally { setLoadingMore(false); } };
  useEffect(() => { void load(); }, []);
  const markAll = async () => { try { await notificationApi.markAllRead(); setItems(rows => rows.map(row => ({ ...row, is_read: true }))); } catch { setError(true); } };
  const markRead = async (id: number) => { try { await notificationApi.markRead(id); setItems(rows => rows.map(row => row.id === id ? { ...row, is_read: true } : row)); } catch { setError(true); } };

  return <div className="space-y-5">
    <PageHeader size="md" title={t('notifications.title')} subtitle={t('notifications.subtitle', { count: unread })} iconElement={<Bell className="size-6" />} primaryAction={<AppButton onClick={() => void markAll()} disabled={unread === 0}><CheckCheck className="size-4" />{t('notifications.markAll')}</AppButton>} />
    {loading ? <LoadingState title={t('notifications.loading')} /> : error && items.length === 0 ? <EmptyState icon={<BellRing />} title={t('notifications.error')} description={t('notifications.errorHelp')} action={<AppButton onClick={() => void load()}>{t('common.retry')}</AppButton>} /> : items.length === 0 ? <EmptyState icon={<Bell />} title={t('notifications.empty')} description={t('notifications.emptyHelp')} /> : <div className="grid gap-3">{items.map(item => <Card key={item.id} className={`p-4 ${item.is_read ? '' : 'border-primary/50 bg-primary-subtle'}`}><button type="button" onClick={() => void markRead(item.id)} disabled={item.is_read} className="flex w-full min-w-0 items-start gap-3 text-left disabled:cursor-default"><span className={`mt-1 size-2 shrink-0 rounded-full ${item.is_read ? 'bg-surface-active' : 'bg-primary'}`} aria-hidden="true" /><span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2"><strong className="text-content-primary">{t(item.title_key, item.interpolation)}</strong>{!item.is_read ? <Badge tone="primary">{t('notifications.unread')}</Badge> : null}</span><span className="mt-1 block text-sm text-content-secondary">{t(item.message_key, item.interpolation)}</span><span className="mt-2 flex items-center gap-1 text-xs text-content-muted"><Clock3 className="size-3" />{new Date(item.created_at).toLocaleString(i18n.language)}</span></span></button></Card>)}{error ? <p className="text-sm text-danger">{t('notifications.errorHelp')}</p> : null}{hasMore ? <AppButton onClick={() => void loadMore()} disabled={loadingMore} variant="secondary" className="mx-auto">{loadingMore ? t('common.loading') : 'Load more'}</AppButton> : null}</div>}
  </div>;
}
