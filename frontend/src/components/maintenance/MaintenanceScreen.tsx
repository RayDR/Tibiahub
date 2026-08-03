import { Clock3, RefreshCw, ShieldCheck, Wrench } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { AppButton, Card } from '../ui';
import type { MaintenanceStatus } from '../../services/maintenanceMode';

export default function MaintenanceScreen({ status, refresh, refreshing }: { status: MaintenanceStatus; refresh: () => void; refreshing: boolean }) {
  const { t } = useTranslation();
  return <main className="min-h-screen bg-app px-4 py-10 text-content-primary sm:grid sm:place-items-center">
    <Card className="mx-auto max-w-2xl p-6 sm:p-10">
      <div className="flex items-center gap-3 text-primary"><Wrench className="size-8" /><span className="text-sm font-semibold uppercase tracking-widest">TibiaHub</span></div>
      <h1 className="mt-7 text-3xl font-bold sm:text-4xl">{t('maintenanceMode.screen.title')}</h1>
      <p className="mt-3 text-content-secondary">{status.message || t('maintenanceMode.screen.defaultMessage')}</p>
      <dl className="mt-7 grid gap-3 rounded-xl bg-surface-base p-4 sm:grid-cols-2">
        <div><dt className="text-xs uppercase text-content-muted">{t('maintenanceMode.screen.started')}</dt><dd className="mt-1 flex items-center gap-2"><Clock3 className="size-4" />{status.started_at ? new Date(status.started_at).toLocaleString() : t('maintenanceMode.common.unknown')}</dd></div>
        <div><dt className="text-xs uppercase text-content-muted">{t('maintenanceMode.screen.expected')}</dt><dd className="mt-1">{status.planned_end_at ? new Date(status.planned_end_at).toLocaleString() : t('maintenanceMode.screen.noEstimate')}</dd></div>
      </dl>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <AppButton onClick={refresh} loading={refreshing}><RefreshCw className="size-4" />{t('maintenanceMode.screen.refresh')}</AppButton>
        <Link className="app-button-secondary" to="/login?maintenance=1"><ShieldCheck className="size-4" />{t('maintenanceMode.screen.adminAccess')}</Link>
      </div>
      <p className="mt-5 text-xs text-content-muted">{t('maintenanceMode.screen.status', { status: status.service_status })}</p>
    </Card>
  </main>;
}
