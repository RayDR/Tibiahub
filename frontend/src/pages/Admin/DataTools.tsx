/**
 * DataTools – consolidated page for API Monitor, durable Full Sync, and Knowledge.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import {
    CheckCircle, XCircle, AlertCircle,
    RefreshCw, Database, Globe, BookOpen, Code,
    Workflow,
} from 'lucide-react';
import KnowledgeOperations from './KnowledgeOperations';
import FullSyncDashboard from './FullSyncDashboard';
import { WorkspaceContentHeader } from '../../components/workspace/WorkspacePrimitives';
import { DegradedState, ErrorState, LoadingState } from '../../components/ui';
import { formatNumber, formatTime } from '../../utils/locale';

type Tab = 'api-monitor' | 'admin-sync' | 'knowledge';

// ── API Monitor types ──────────────────────────────────────────────────────────
interface APIStatus {
    name: string;
    url: string;
    status: 'online' | 'offline' | 'error';
    status_code?: number;
    latency_ms?: number;
    error?: string;
    sample_data?: any;
    full_response?: any;
}
interface APIMonitorResponse {
    timestamp: string;
    total_apis: number;
    online_count: number;
    apis: APIStatus[];
}

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

function authHeader() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
}

function getStatusIcon(status: string) {
    if (status === 'online' || status === 'success') return <CheckCircle className="w-4 h-4 text-success" />;
    if (status === 'offline' || status === 'error') return <XCircle className="w-4 h-4 text-danger" />;
    return <AlertCircle className="w-4 h-4 text-primary" />;
}

// ── API Monitor tab ────────────────────────────────────────────────────────────
function APIMonitorTab() {
    const { t, i18n } = useTranslation();
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<APIMonitorResponse | null>(null);
    const [error, setError] = useState(false);
    const [expandedAPI, setExpandedAPI] = useState<string | null>(null);

    const load = async () => {
        setLoading(true);
        setError(false);
        try {
            const response = await axios.get<APIMonitorResponse>(
                `${API_BASE}/guild-management/api-monitor`,
                { headers: authHeader() }
            );
            setData(response.data);
        } catch { setError(true); }
        finally { setLoading(false); }
    };

    useEffect(() => { void load(); }, []);

    if (loading && !data) return <LoadingState title={t('adminDataTools.monitor.loading')} />;
    if (error && !data) return <ErrorState title={t('adminDataTools.monitor.error')} description={t('adminDataTools.monitor.errorHelp')} action={<button type="button" onClick={() => void load()} className="app-button-secondary">{t('common.retry')}</button>} />;

    return (
        <div className="space-y-4">
            {error ? <DegradedState title={t('adminDataTools.monitor.degraded')} description={t('adminDataTools.monitor.degradedHelp')} action={<button type="button" onClick={() => void load()} className="app-button-secondary app-button-sm">{t('common.retry')}</button>} /> : null}
            <div className="flex items-center justify-between">
                {data && (
                    <div className="flex gap-4 text-sm text-content-secondary">
                        <span>{t('adminDataTools.monitor.apiCount', { value: formatNumber(data.total_apis, i18n.resolvedLanguage || i18n.language) })}</span>
                        <span>{t('adminDataTools.monitor.onlineCount', { value: formatNumber(data.online_count, i18n.resolvedLanguage || i18n.language) })}</span>
                        <span>{t('adminDataTools.monitor.checked', { time: formatTime(data.timestamp, i18n.resolvedLanguage || i18n.language) })}</span>
                    </div>
                )}
                <button onClick={load} className="flex items-center gap-1 rounded border border-line px-3 py-1.5 text-sm text-content-secondary hover:text-content-primary">
                    <RefreshCw className="w-3.5 h-3.5" /> {t('common.refresh')}
                </button>
            </div>
            <div className="space-y-3">
                {data?.apis.map((api, i) => (
                    <div key={i} className={`rounded-lg border p-4 ${api.status === 'online' ? 'border-success/20 bg-success/5' : api.status === 'offline' ? 'border-danger/20 bg-danger/5' : 'border-primary/20 bg-primary/5'}`}>
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex items-center gap-3">
                                {api.name.includes('TibiaData') ? <Database className="w-5 h-5 text-info" /> :
                                    api.name.includes('Wiki') || api.name.includes('Fandom') ? <BookOpen className="w-5 h-5 text-accent" /> :
                                        <Globe className="w-5 h-5 text-primary" />}
                                <div>
                                    <div className="font-medium text-content-primary">{api.name}</div>
                                    <div className="text-xs text-content-muted font-mono">{api.url}</div>
                                </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                                {getStatusIcon(api.status)}
                                {api.latency_ms !== undefined && <span className="text-xs text-content-muted">{api.latency_ms}ms</span>}
                                {api.status_code && <span className="text-xs text-content-muted">HTTP {api.status_code}</span>}
                            </div>
                        </div>
                        {api.error && <div className="mt-2 text-xs text-danger bg-danger/20 rounded px-2 py-1">{api.error}</div>}
                        {api.full_response && (
                            <div className="mt-2">
                                <button onClick={() => setExpandedAPI(expandedAPI === api.name ? null : api.name)} className="text-xs text-primary hover:text-primary flex items-center gap-1">
                                    <Code className="w-3.5 h-3.5" /> {expandedAPI === api.name ? t('adminDataTools.monitor.hideResponse') : t('adminDataTools.monitor.showResponse')}
                                </button>
                                {expandedAPI === api.name && (
                                    <pre className="mt-2 text-xs text-success bg-surface-base rounded p-3 overflow-x-auto max-h-64 overflow-y-auto">
                                        {JSON.stringify(api.full_response, null, 2)}
                                    </pre>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

function AdminSyncTab() {
    return <FullSyncDashboard />;
}

// ── Main DataTools component ───────────────────────────────────────────────────
export default function DataTools({ initialTab = 'api-monitor' }: { initialTab?: Tab }) {
    const { t } = useTranslation();
    const [activeTab, setActiveTab] = useState<Tab>(initialTab);

    const tabs: { id: Tab; label: string; icon: any; description: string }[] = [
        { id: 'api-monitor', label: t('adminDataTools.tabs.monitor'), icon: Globe, description: t('adminDataTools.tabs.monitorHelp') },
        { id: 'admin-sync', label: t('adminDataTools.tabs.sync'), icon: RefreshCw, description: t('adminDataTools.tabs.syncHelp') },
        { id: 'knowledge', label: t('knowledgeOps.navigation'), icon: Workflow, description: t('knowledgeOps.subtitle') },
    ];

    return (
        <div className="workspace-page">
            <WorkspaceContentHeader
                title={t('adminDataTools.title')}
                description={t('adminDataTools.subtitle')}
                icon={<Database />}
            />

            {/* Tabs */}
            <div className="flex gap-1 border-b border-line">
                {tabs.map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={`flex items-center gap-2 px-4 py-2.5 border-b-2 text-sm font-medium transition-colors ${
                            activeTab === id
                                ? 'border-primary text-primary'
                                : 'border-transparent text-content-secondary hover:text-content-primary'
                        }`}
                    >
                        <Icon className="w-4 h-4" />
                        {label}
                    </button>
                ))}
            </div>

            {/* Tab content */}
            <div>
                {activeTab === 'api-monitor' && <APIMonitorTab />}
                {activeTab === 'admin-sync' && <AdminSyncTab />}
                {activeTab === 'knowledge' && <KnowledgeOperations />}
            </div>
        </div>
    );
}
