import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { 
    Activity, CheckCircle, XCircle, AlertCircle, 
    Loader2, RefreshCw, Database, Globe, BookOpen,
    Clock, Code
} from 'lucide-react';
import axios from 'axios';
import { faChartLine } from '@fortawesome/free-solid-svg-icons';
import PageHeader from '../../components/ui/PageHeader';
import AppButton from '../../components/ui/AppButton';

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

export default function APIMonitor() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<APIMonitorResponse | null>(null);
    const [expandedAPI, setExpandedAPI] = useState<string | null>(null);
    const [refreshing, setRefreshing] = useState(false);
    const [syncingUp, setSyncingUp] = useState(false);

    // Check permissions
    useEffect(() => {
        if (!user?.is_superuser && user?.guild_rank !== 'Alpha Warbringer' && user?.guild_rank !== 'Bloodhowl Marshal') {
            navigate('/guild');
        }
    }, [user, navigate]);

    const loadAPIStatus = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get<APIMonitorResponse>(
                `${import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'}/guild-management/api-monitor`,
                {
                    headers: { Authorization: `Bearer ${token}` }
                }
            );
            setData(response.data);
        } catch (error) {
            console.error('Failed to load API status:', error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        loadAPIStatus();
    }, []);

    const handleRefresh = () => {
        setRefreshing(true);
        loadAPIStatus();
    };

    const handleSyncUp = async () => {
        try {
            setSyncingUp(true);
            const token = localStorage.getItem('token');
            await axios.post(
                `${import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'}/admin/sync/bestiary/start?source=all&mode=auto`,
                {},
                {
                    headers: { Authorization: `Bearer ${token}` }
                }
            );
        } catch (error) {
            console.error('Failed to trigger sync-up:', error);
        } finally {
            setSyncingUp(false);
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'online': return <CheckCircle className="w-5 h-5 text-green-400" />;
            case 'offline': return <XCircle className="w-5 h-5 text-red-400" />;
            case 'error': return <AlertCircle className="w-5 h-5 text-yellow-400" />;
            default: return <Activity className="w-5 h-5 text-gray-400" />;
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'online': return 'bg-green-500/10 border-green-500/30';
            case 'offline': return 'bg-red-500/10 border-red-500/30';
            case 'error': return 'bg-yellow-500/10 border-yellow-500/30';
            default: return 'bg-gray-500/10 border-gray-500/30';
        }
    };

    const getAPIIcon = (name: string) => {
        if (name.includes('TibiaData')) return <Database className="w-6 h-6 text-blue-400" />;
        if (name.includes('TibiaWiki') || name.includes('Fandom')) return <BookOpen className="w-6 h-6 text-purple-400" />;
        if (name.includes('Tibia.com') || name.includes('Official')) return <Globe className="w-6 h-6 text-amber-400" />;
        return <Database className="w-6 h-6 text-slate-400" />;
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
            </div>
        );
    }

    return (
        <div className="container mx-auto px-4 py-8 max-w-7xl">
            {/* Header */}
            <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <PageHeader
                    title="API Monitor"
                    subtitle="Monitor external APIs and database health"
                    icon={faChartLine}
                    align="left"
                    size="md"
                />
                <div className="flex items-center gap-2">
                    <AppButton
                        onClick={handleSyncUp}
                        disabled={syncingUp}
                        className="inline-flex items-center gap-2"
                    >
                        <RefreshCw className={`w-4 h-4 ${syncingUp ? 'animate-spin' : ''}`} />
                        Sync-up
                    </AppButton>
                    <AppButton
                        onClick={handleRefresh}
                        disabled={refreshing}
                        className="inline-flex items-center gap-2"
                    >
                        <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                        Refresh
                    </AppButton>
                </div>
            </div>

            {/* Summary Stats */}
            {data && (
                <div className="grid md:grid-cols-3 gap-4 mb-8">
                    <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-slate-400 text-sm mb-1">Total APIs</p>
                                <p className="text-3xl font-bold text-white">{data.total_apis}</p>
                            </div>
                            <Database className="w-8 h-8 text-slate-500" />
                        </div>
                    </div>

                    <div className="bg-slate-900 border border-green-500/30 rounded-xl p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-slate-400 text-sm mb-1">Online</p>
                                <p className="text-3xl font-bold text-green-400">{data.online_count}</p>
                            </div>
                            <CheckCircle className="w-8 h-8 text-green-500" />
                        </div>
                    </div>

                    <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-slate-400 text-sm mb-1">Last Check</p>
                                <p className="text-sm font-medium text-white">
                                    {new Date(data.timestamp).toLocaleTimeString()}
                                </p>
                            </div>
                            <Clock className="w-8 h-8 text-slate-500" />
                        </div>
                    </div>
                </div>
            )}

            {/* API Status Cards */}
            <div className="grid gap-4">
                {data?.apis.map((api, index) => (
                    <div
                        key={index}
                        className={`bg-slate-900 border rounded-xl p-6 ${getStatusColor(api.status)}`}
                    >
                        <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                                {getAPIIcon(api.name)}
                                <div>
                                    <h3 className="text-xl font-bold text-white">{api.name}</h3>
                                    <p className="text-sm text-slate-400 font-mono">{api.url}</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {getStatusIcon(api.status)}
                                <span className={`text-sm font-medium ${
                                    api.status === 'online' ? 'text-green-400' : 
                                    api.status === 'offline' ? 'text-red-400' : 'text-yellow-400'
                                }`}>
                                    {api.status.toUpperCase()}
                                </span>
                            </div>
                        </div>

                        {/* Status Details */}
                        <div className="grid md:grid-cols-3 gap-4 mb-4">
                            {api.status_code && (
                                <div className="bg-slate-800/50 rounded-lg p-3">
                                    <p className="text-xs text-slate-400 mb-1">Status Code</p>
                                    <p className="text-lg font-mono text-white">{api.status_code}</p>
                                </div>
                            )}
                            {api.latency_ms !== undefined && (
                                <div className="bg-slate-800/50 rounded-lg p-3">
                                    <p className="text-xs text-slate-400 mb-1">Latency</p>
                                    <p className="text-lg font-mono text-white">{api.latency_ms}ms</p>
                                </div>
                            )}
                            {api.error && (
                                <div className="bg-red-900/20 rounded-lg p-3 md:col-span-3">
                                    <p className="text-xs text-red-400 mb-1">Error</p>
                                    <p className="text-sm font-mono text-red-300">{api.error}</p>
                                </div>
                            )}
                        </div>

                        {/* Sample Data */}
                        {api.sample_data && (
                            <div className="bg-slate-800/50 rounded-lg p-4 mb-3">
                                <p className="text-xs text-slate-400 mb-2 font-semibold">Sample Data</p>
                                <pre className="text-xs text-emerald-400 font-mono overflow-x-auto">
                                    {JSON.stringify(api.sample_data, null, 2)}
                                </pre>
                            </div>
                        )}

                        {/* Full Response Toggle */}
                        {api.full_response && (
                            <div>
                                <button
                                    onClick={() => setExpandedAPI(expandedAPI === api.name ? null : api.name)}
                                    className="flex items-center gap-2 text-sm text-amber-400 hover:text-amber-300 transition-colors"
                                >
                                    <Code className="w-4 h-4" />
                                    {expandedAPI === api.name ? 'Hide' : 'Show'} Full JSON Response
                                </button>

                                {expandedAPI === api.name && (
                                    <div className="mt-3 bg-slate-950 rounded-lg p-4 border border-slate-700">
                                        <pre className="text-xs text-green-400 font-mono overflow-x-auto max-h-96 overflow-y-auto">
                                            {JSON.stringify(api.full_response, null, 2)}
                                        </pre>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
