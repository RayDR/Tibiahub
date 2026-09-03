import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { WorkspaceContentHeader } from '../../components/workspace/WorkspacePrimitives';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui';
import RaffleCreationWizard from '../../components/raffle/RaffleCreationWizard';
import { raffleApi, RaffleWorkspaceItem } from '../../services/raffle';

export default function GlobalActivities() {
  const { t } = useTranslation(); const [items, setItems] = useState<RaffleWorkspaceItem[]>([]); const [error, setError] = useState(false); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => { setLoading(true); setError(false); try { setItems((await raffleApi.workspace()).filter(item => item.scope_type !== 'guild')); } catch { setError(true); } finally { setLoading(false); } }, []);
  useEffect(() => { void load(); }, [load]);
  return <div className="space-y-4"><WorkspaceContentHeader title={t('raffle.global.title')} description={t('raffle.global.subtitle')} /><RaffleCreationWizard isGlobalAdmin onCreated={() => void load()} />{loading ? <LoadingState title={t('workspace.common.loading')} /> : error ? <ErrorState title={t('raffle.workspace.errors.title')} description={t('raffle.workspace.errors.help')} action={<button type="button" onClick={() => void load()} className="app-button-secondary">{t('common.retry')}</button>} /> : items.length === 0 ? <EmptyState title={t('raffle.global.title')} description={t('raffle.workspace.errors.help')} /> : <div className="grid gap-3 sm:grid-cols-2">{items.map(item => <article key={item.id} className="rounded-xl border border-line p-4"><span className="rounded-full bg-info/15 px-2 py-1 text-xs text-info">{t(`raffle.workspace.scopes.${item.scope_type}.title`)}</span><h3 className="mt-3 font-semibold">{item.title}</h3><p className="text-sm text-content-secondary">{item.world_name || t('raffle.global.crossServer')}</p></article>)}</div>}</div>;
}
