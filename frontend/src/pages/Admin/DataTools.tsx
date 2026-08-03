/**
 * DataTools – consolidated page for API Monitor, Database Sync, and Admin Sync.
 * Replaces three separate admin pages with a single tabbed interface.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useToast } from '../../context/ToastContext';
import {
    CheckCircle, XCircle, AlertCircle, Loader2,
    RefreshCw, Database, Globe, BookOpen, Code,
    GitBranch, Download, Eye,
    Workflow,
} from 'lucide-react';
import KnowledgeOperations from './KnowledgeOperations';
import FullSyncDashboard from './FullSyncDashboard';

type Tab = 'api-monitor' | 'db-sync' | 'admin-sync' | 'knowledge';

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

// ── DB Sync types ──────────────────────────────────────────────────────────────
interface SyncChange {
    timestamp: string;
    change_type: string;
    source_api: string;
    entity: string;
    entity_id: number;
    action: string;
    old_data?: any;
    new_data?: any;
    status: string;
    approval_required: boolean;
}
interface SyncPreview {
    status: string;
    message: string;
    backup_created: boolean;
    total_changes: number;
    pending_approvals: number;
    changes: SyncChange[];
    action_required: boolean;
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
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<APIMonitorResponse | null>(null);
    const [expandedAPI, setExpandedAPI] = useState<string | null>(null);

    const load = async () => {
        setLoading(true);
        try {
            const response = await axios.get<APIMonitorResponse>(
                `${API_BASE}/guild-management/api-monitor`,
                { headers: authHeader() }
            );
            setData(response.data);
        } catch { /* ignore */ }
        finally { setLoading(false); }
    };

    useEffect(() => { void load(); }, []);

    if (loading) return <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                {data && (
                    <div className="flex gap-4 text-sm text-content-secondary">
                        <span><span className="text-content-primary font-medium">{data.total_apis}</span> APIs</span>
                        <span><span className="text-success font-medium">{data.online_count}</span> online</span>
                        <span>checked {new Date(data.timestamp).toLocaleTimeString()}</span>
                    </div>
                )}
                <button onClick={load} className="flex items-center gap-1 rounded border border-line px-3 py-1.5 text-sm text-content-secondary hover:text-content-primary">
                    <RefreshCw className="w-3.5 h-3.5" /> Refresh
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
                                    <Code className="w-3.5 h-3.5" /> {expandedAPI === api.name ? 'Hide' : 'Show'} full response
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

// ── Database Sync tab ──────────────────────────────────────────────────────────
function DBSyncTab() {
    const toast = useToast();
    const [loading, setLoading] = useState(false);
    const [preview, setPreview] = useState<SyncPreview | null>(null);
    const [selectedChanges, setSelectedChanges] = useState<number[]>([]);

    const handlePreview = async () => {
        setLoading(true);
        try {
            const response = await axios.post<SyncPreview>(`${API_BASE}/sync/preview`, {}, { headers: authHeader() });
            setPreview(response.data);
            setSelectedChanges([]);
            toast.success('Preview loaded');
        } catch {
            toast.error('Failed to preview changes');
        } finally {
            setLoading(false);
        }
    };

    const handleApprove = async (approveAll: boolean) => {
        setLoading(true);
        try {
            await axios.post(`${API_BASE}/sync/approve`, {}, {
                params: { approve_all: approveAll, change_indices: approveAll ? undefined : selectedChanges },
                headers: authHeader(),
            });
            toast.success('Changes approved and applied');
            setPreview(null);
            setSelectedChanges([]);
        } catch {
            toast.error('Failed to apply changes');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3">
                <button
                    onClick={handlePreview}
                    disabled={loading}
                    className="flex items-center gap-2 rounded-md bg-info px-4 py-2 text-sm font-medium text-content-on-primary hover:bg-info-hover disabled:opacity-50"
                >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
                    Preview Changes
                </button>
                {preview && preview.changes.length > 0 && (
                    <>
                        <button
                            onClick={() => void handleApprove(false)}
                            disabled={loading || selectedChanges.length === 0}
                            className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-content-on-primary hover:bg-primary-hover disabled:opacity-50"
                        >
                            <Download className="w-4 h-4" /> Apply Selected ({selectedChanges.length})
                        </button>
                        <button
                            onClick={() => void handleApprove(true)}
                            disabled={loading}
                            className="flex items-center gap-2 rounded-md bg-success px-4 py-2 text-sm font-medium text-content-on-primary hover:bg-success-hover disabled:opacity-50"
                        >
                            <CheckCircle className="w-4 h-4" /> Apply All
                        </button>
                    </>
                )}
            </div>

            {preview && (
                <div className="space-y-3">
                    <div className="flex gap-4 text-sm text-content-secondary">
                        <span><span className="text-content-primary font-medium">{preview.total_changes}</span> changes</span>
                        <span><span className="text-primary font-medium">{preview.pending_approvals}</span> need approval</span>
                        {preview.backup_created && <span className="text-success">✓ Backup created</span>}
                    </div>
                    {preview.changes.length === 0 ? (
                        <div className="text-center py-8 text-content-muted bg-surface-base/50 rounded-lg border border-line">No pending changes.</div>
                    ) : (
                        <div className="bg-surface-base/50 border border-line rounded-lg overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead className="bg-surface-base/50">
                                        <tr>
                                            <th className="p-3 text-left"><input type="checkbox" onChange={(e) => setSelectedChanges(e.target.checked ? preview.changes.map((_, i) => i) : [])} checked={selectedChanges.length === preview.changes.length} /></th>
                                            <th className="p-3 text-left text-xs uppercase text-content-secondary">Entity</th>
                                            <th className="p-3 text-left text-xs uppercase text-content-secondary">Action</th>
                                            <th className="p-3 text-left text-xs uppercase text-content-secondary">Source</th>
                                            <th className="p-3 text-left text-xs uppercase text-content-secondary">Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {preview.changes.map((change, i) => (
                                            <tr key={i} className="border-t border-line">
                                                <td className="p-3"><input type="checkbox" checked={selectedChanges.includes(i)} onChange={() => setSelectedChanges((prev) => prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i])} /></td>
                                                <td className="p-3 text-sm text-content-primary">{change.entity}</td>
                                                <td className="p-3 text-sm text-content-secondary">{change.action}</td>
                                                <td className="p-3 text-xs text-content-secondary">{change.source_api}</td>
                                                <td className="p-3 text-xs">
                                                    <span className={`px-2 py-1 rounded ${change.approval_required ? 'bg-primary/15 text-primary' : 'bg-surface text-content-secondary'}`}>
                                                        {change.status}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}
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
        { id: 'api-monitor', label: 'API Monitor', icon: Globe, description: 'External API health checks' },
        { id: 'db-sync', label: 'Database Sync', icon: GitBranch, description: 'Preview and apply DB changes' },
        { id: 'admin-sync', label: 'Data Sync', icon: RefreshCw, description: 'Trigger bestiary syncs' },
        { id: 'knowledge', label: t('knowledgeOps.navigation'), icon: Workflow, description: t('knowledgeOps.subtitle') },
    ];

    return (
        <div className="space-y-4">
            <div className="bg-surface-base/50 border border-line rounded-lg p-4">
                <div className="flex items-center gap-3 mb-1">
                    <Database className="w-5 h-5 text-primary" />
                    <h1 className="text-xl font-semibold text-content-primary">Data Tools</h1>
                </div>
                <p className="text-sm text-content-secondary">API monitoring, database sync previews, and bestiary data updates — all in one place.</p>
            </div>

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
                {activeTab === 'db-sync' && <DBSyncTab />}
                {activeTab === 'admin-sync' && <AdminSyncTab />}
                {activeTab === 'knowledge' && <KnowledgeOperations />}
            </div>
        </div>
    );
}
