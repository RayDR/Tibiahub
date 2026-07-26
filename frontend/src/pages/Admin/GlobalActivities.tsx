import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { WorkspaceHeader, EmptyState } from '../../components/workspace/WorkspacePrimitives';
import RaffleCreationWizard from '../../components/raffle/RaffleCreationWizard';
import { raffleApi, RaffleWorkspaceItem } from '../../services/raffle';

export default function GlobalActivities() {
  const { t } = useTranslation(); const [items, setItems] = useState<RaffleWorkspaceItem[]>([]); const [error, setError] = useState(false);
  const load = useCallback(async () => { try { setItems((await raffleApi.workspace()).filter(item => item.scope_type !== 'guild')); } catch { setError(true); } }, []);
  useEffect(() => { void load(); }, [load]);
  return <div className="space-y-4"><WorkspaceHeader title={t('raffle.global.title')} subtitle={t('raffle.global.subtitle')} badge={t('workspace.admin.badge')} /><RaffleCreationWizard isGlobalAdmin onCreated={() => void load()} />{error ? <EmptyState title={t('raffle.workspace.errors.title')} description={t('raffle.workspace.errors.help')} /> : <div className="grid gap-3 sm:grid-cols-2">{items.map(item => <article key={item.id} className="rounded-xl border border-line p-4"><span className="rounded-full bg-info/15 px-2 py-1 text-xs text-info">{t(`raffle.workspace.scopes.${item.scope_type}.title`)}</span><h2 className="mt-3 font-semibold">{item.title}</h2><p className="text-sm text-content-secondary">{item.world_name || t('raffle.global.crossServer')}</p></article>)}</div>}</div>;
}
