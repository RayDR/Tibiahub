import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

interface SyncLog {
  id: number;
  api_name: string;
  endpoint: string;
  status: 'pending' | 'running' | 'success' | 'error';
  source?: string;
  total_items?: number;
  processed_items: number;
  error_count: number;
  message?: string;
  error_details?: string;
  started_at: string;
  completed_at?: string;
}

interface SyncStats {
  creatures: number;
  items: number;
  hunting_places: number;
  quests: number;
  sync_logs: number;
}

interface DataComparison {
  field: string;
  old_value: any;
  new_value: any;
  different: boolean;
}

interface ConflictResolution {
  api_name: string;
  item_name: string;
  conflicts: DataComparison[];
  action: 'skip' | 'overwrite' | 'pending';
}

interface SyncRuntimeSettings {
  bestiary_cache_only_reads: boolean;
  bestiary_allow_external_detail_fallback: boolean;
  bestiary_search_page_size: number;
  sync_cooldown_minutes: number;
}

interface SyncJobStatus {
  job_id: string;
  target: string;
  mode: string;
  status: 'queued' | 'running' | 'success' | 'error';
  created_at: string;
  finished_at?: string;
  error?: string;
  results?: Record<string, any>;
}

const DataSyncPanel: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'sync' | 'logs' | 'stats'>('sync');
  const [syncLogs, setSyncLogs] = useState<SyncLog[]>([]);
  const [stats, setStats] = useState<SyncStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedLog, setSelectedLog] = useState<number | null>(null);
  const [syncingApis, setSyncingApis] = useState<Set<string>>(new Set());
  const [conflicts, setConflicts] = useState<ConflictResolution[]>([]);
  const [showConflictModal, setShowConflictModal] = useState(false);
  const [syncMode, setSyncMode] = useState<'auto' | 'compare'>('compare');
  const [runtimeSettings, setRuntimeSettings] = useState<SyncRuntimeSettings | null>(null);
  const [activeJobs, setActiveJobs] = useState<Record<string, string>>({});

  const API_BASE = '/api/v1';

  const syncApis = [
    { name: 'creatures', icon: '🐉', label: 'Criaturas', description: 'Sincronizar bestias y monstruos' },
    { name: 'items', icon: '⚔️', label: 'Items', description: 'Sincronizar armas, armaduras y objetos' },
    { name: 'hunting-places', icon: '🗺️', label: 'Zonas de Hunt', description: 'Sincronizar lugares de caza' },
    { name: 'quests', icon: '📜', label: 'Quests', description: 'Sincronizar misiones y recompensas' },
  ];

  useEffect(() => {
    loadSyncLogs();
    loadStats();
    loadRuntimeSettings();

    // Auto-refresh cada 5 segundos
    const interval = setInterval(() => {
      if (syncingApis.size > 0) {
        loadSyncLogs();
        loadStats();
        void pollActiveJobs();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [syncingApis]);

  const getAuthToken = () => {
    return localStorage.getItem('token') || '';
  };

  const loadSyncLogs = async () => {
    try {
      const response = await fetch(`${API_BASE}/admin/sync/logs`, {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSyncLogs(data);
      }
    } catch (error) {
      console.error('Error loading sync logs:', error);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/admin/sync/stats`, {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const loadRuntimeSettings = async () => {
    try {
      const response = await fetch(`${API_BASE}/admin/sync/settings`, {
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setRuntimeSettings(data);
      }
    } catch (error) {
      console.error('Error loading sync runtime settings:', error);
    }
  };

  const updateRuntimeSettings = async (patch: Partial<SyncRuntimeSettings>) => {
    if (!runtimeSettings) return;
    try {
      const response = await fetch(`${API_BASE}/admin/sync/settings`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(patch)
      });
      if (response.ok) {
        const data = await response.json();
        setRuntimeSettings(data);
      }
    } catch (error) {
      console.error('Error updating sync runtime settings:', error);
    }
  };

  const startSync = async (apiName: string) => {
    if (syncingApis.has(apiName)) {
      alert('⚠️ Esta sincronización ya está en proceso');
      return;
    }

    setLoading(true);
    setSyncingApis(prev => new Set(prev).add(apiName));

    try {
      const response = await fetch(`${API_BASE}/admin/sync/bestiary/start?source=${encodeURIComponent(apiName)}&mode=${encodeURIComponent(syncMode)}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const result = await response.json();
        if (result.job_id) {
          setActiveJobs(prev => ({ ...prev, [apiName]: result.job_id }));
        }
        alert(`✅ Sync started for ${apiName}`);
        loadSyncLogs();
      } else {
        alert(`❌ Error al iniciar sincronización de ${apiName}`);
        setSyncingApis(prev => {
          const newSet = new Set(prev);
          newSet.delete(apiName);
          return newSet;
        });
      }
    } catch (error) {
      console.error('Error starting sync:', error);
      alert('❌ Error de conexión');
      setSyncingApis(prev => {
        const newSet = new Set(prev);
        newSet.delete(apiName);
        return newSet;
      });
    } finally {
      setLoading(false);
    }
  };

  const pollActiveJobs = async () => {
    const entries = Object.entries(activeJobs);
    if (entries.length === 0) return;

    for (const [apiName, jobId] of entries) {
      try {
        const response = await fetch(`${API_BASE}/admin/sync/jobs/${jobId}`, {
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`,
          }
        });
        if (!response.ok) continue;
        const job = await response.json() as SyncJobStatus;
        if (job.status === 'success' || job.status === 'error') {
          setSyncingApis(prev => {
            const newSet = new Set(prev);
            newSet.delete(apiName);
            return newSet;
          });
          setActiveJobs(prev => {
            const next = { ...prev };
            delete next[apiName];
            return next;
          });
          if (job.status === 'error') {
            alert(`❌ Sync failed for ${apiName}`);
          }
        }
      } catch (error) {
        console.error('Error polling sync job:', error);
      }
    }
  };

  const resolveConflicts = async (action: 'skip_all' | 'overwrite_all') => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/admin/sync/resolve-conflicts`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getAuthToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          conflicts: conflicts,
          action: action
        })
      });

      if (response.ok) {
        alert(`✅ Conflictos resueltos: ${action === 'skip_all' ? 'Omitir todos' : 'Sobrescribir todos'}`);
        setShowConflictModal(false);
        setConflicts([]);
        loadSyncLogs();
        loadStats();
      } else {
        alert('❌ Error al resolver conflictos');
      }
    } catch (error) {
      console.error('Error resolving conflicts:', error);
      alert('❌ Error de conexión');
    } finally {
      setLoading(false);
    }
  };

  const getLogProgress = (log: SyncLog): number => {
    if (!log.total_items || log.total_items === 0) return 0;
    return Math.round((log.processed_items / log.total_items) * 100);
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'success': return 'text-green-400';
      case 'error': return 'text-red-400';
      case 'running': return 'text-blue-400';
      default: return 'text-yellow-400';
    }
  };

  const getStatusIcon = (status: string): string => {
    switch (status) {
      case 'success': return '✅';
      case 'error': return '❌';
      case 'running': return '⏳';
      default: return '⏸️';
    }
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="min-h-screen py-6 sm:py-12 px-3 sm:px-4">
      <div className="container mx-auto max-w-7xl">
        {/* Header */}
        <div className="text-center mb-8 sm:mb-12 fade-in">
          <h1 className="text-3xl sm:text-5xl font-bold mb-3 sm:mb-4 bg-gradient-to-r from-blue-400 via-cyan-500 to-teal-600 bg-clip-text text-transparent">
            🔄 Sincronización de Datos
          </h1>
          <p className="text-gray-300 text-base sm:text-lg">
            Gestiona la sincronización con APIs externas
          </p>
        </div>

        {/* Mode Selector */}
        <div className="card mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white mb-1">Modo de Sincronización</h3>
              <p className="text-sm text-gray-400">Elige cómo manejar conflictos de datos</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setSyncMode('auto')}
                className={`px-4 py-2 rounded-lg font-semibold transition-all ${syncMode === 'auto'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
              >
                ⚡ Automático
              </button>
              <button
                onClick={() => setSyncMode('compare')}
                className={`px-4 py-2 rounded-lg font-semibold transition-all ${syncMode === 'compare'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
              >
                🔍 Comparar
              </button>
            </div>
          </div>
          <div className="mt-4 text-sm text-gray-400">
            {syncMode === 'auto'
              ? '⚡ Sobrescribirá datos automáticamente sin confirmación'
              : '🔍 Te mostrará los conflictos antes de sobrescribir'}
          </div>
        </div>

        {runtimeSettings && (
          <div className="card mb-6">
            <h3 className="text-lg font-semibold text-white mb-4">⚙️ Cache & Sync Runtime</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="flex items-center justify-between gap-3 rounded-lg border border-gray-700 p-3">
                <span className="text-sm text-gray-200">Cache-only reads (Bestiary)</span>
                <input
                  type="checkbox"
                  checked={runtimeSettings.bestiary_cache_only_reads}
                  onChange={(event) => void updateRuntimeSettings({ bestiary_cache_only_reads: event.target.checked })}
                />
              </label>
              <label className="flex items-center justify-between gap-3 rounded-lg border border-gray-700 p-3">
                <span className="text-sm text-gray-200">Allow external detail fallback</span>
                <input
                  type="checkbox"
                  checked={runtimeSettings.bestiary_allow_external_detail_fallback}
                  onChange={(event) => void updateRuntimeSettings({ bestiary_allow_external_detail_fallback: event.target.checked })}
                />
              </label>
              <label className="rounded-lg border border-gray-700 p-3">
                <div className="text-sm text-gray-200 mb-2">Bestiary page size</div>
                <input
                  type="number"
                  min={10}
                  max={100}
                  value={runtimeSettings.bestiary_search_page_size}
                  onChange={(event) => {
                    const value = Number(event.target.value || 20);
                    setRuntimeSettings({ ...runtimeSettings, bestiary_search_page_size: value });
                  }}
                  onBlur={() => void updateRuntimeSettings({ bestiary_search_page_size: runtimeSettings.bestiary_search_page_size })}
                  className="w-full rounded bg-gray-800 border border-gray-700 px-3 py-2 text-white"
                />
              </label>
              <label className="rounded-lg border border-gray-700 p-3">
                <div className="text-sm text-gray-200 mb-2">Sync cooldown (minutes)</div>
                <input
                  type="number"
                  min={1}
                  max={1440}
                  value={runtimeSettings.sync_cooldown_minutes}
                  onChange={(event) => {
                    const value = Number(event.target.value || 30);
                    setRuntimeSettings({ ...runtimeSettings, sync_cooldown_minutes: value });
                  }}
                  onBlur={() => void updateRuntimeSettings({ sync_cooldown_minutes: runtimeSettings.sync_cooldown_minutes })}
                  className="w-full rounded bg-gray-800 border border-gray-700 px-3 py-2 text-white"
                />
              </label>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 sm:gap-4 mb-6 sm:mb-8 justify-center">
          <button
            onClick={() => setActiveTab('sync')}
            className={`px-4 sm:px-8 py-2 sm:py-3 rounded-xl font-semibold transition-all duration-300 text-sm sm:text-base ${activeTab === 'sync'
                ? 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white shadow-glow'
                : 'bg-glass-bg border-2 border-glass-border text-white hover:border-blue-500'
              }`}
          >
            🔄 Sincronizar
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`px-4 sm:px-8 py-2 sm:py-3 rounded-xl font-semibold transition-all duration-300 text-sm sm:text-base ${activeTab === 'logs'
                ? 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white shadow-glow'
                : 'bg-glass-bg border-2 border-glass-border text-white hover:border-blue-500'
              }`}
          >
            📋 Logs
          </button>
          <button
            onClick={() => setActiveTab('stats')}
            className={`px-4 sm:px-8 py-2 sm:py-3 rounded-xl font-semibold transition-all duration-300 text-sm sm:text-base ${activeTab === 'stats'
                ? 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white shadow-glow'
                : 'bg-glass-bg border-2 border-glass-border text-white hover:border-blue-500'
              }`}
          >
            📊 Estadísticas
          </button>
        </div>

        {/* Sync Tab */}
        {activeTab === 'sync' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 fade-in">
            {syncApis.map((api) => {
              const isSyncing = syncingApis.has(api.name);
              const latestLog = syncLogs.find(log => log.api_name === api.name && log.status === 'running');

              return (
                <div key={api.name} className="card hover:border-blue-500/50 transition-all">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-2xl font-bold text-white mb-1">
                        {api.icon} {api.label}
                      </h3>
                      <p className="text-sm text-gray-400">{api.description}</p>
                    </div>
                    {isSyncing && (
                      <span className="px-3 py-1 bg-blue-600 text-white text-xs rounded-full animate-pulse">
                        Sincronizando...
                      </span>
                    )}
                  </div>

                  {latestLog && isSyncing && (
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-gray-400 mb-2">
                        <span>Progreso: {latestLog.processed_items}/{latestLog.total_items || 0}</span>
                        <span>{getLogProgress(latestLog)}%</span>
                      </div>
                      <div className="w-full bg-gray-700 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${getLogProgress(latestLog)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  <button
                    onClick={() => startSync(api.name)}
                    disabled={loading || isSyncing}
                    className={`w-full py-3 rounded-xl font-semibold transition-all ${loading || isSyncing
                        ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                        : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white shadow-lg hover:shadow-xl'
                      }`}
                  >
                    {isSyncing ? '⏳ Sincronizando...' : '▶️ Iniciar Sincronización'}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div className="fade-in">
            <div className="card">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-white">📋 Historial de Sincronizaciones</h2>
                <button
                  onClick={loadSyncLogs}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg font-semibold text-white transition-all"
                >
                  🔄 Actualizar
                </button>
              </div>

              {syncLogs.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">📭</div>
                  <p className="text-gray-400">No hay sincronizaciones registradas</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {syncLogs.map((log) => (
                    <div
                      key={log.id}
                      className={`border-2 rounded-xl p-4 transition-all cursor-pointer ${selectedLog === log.id
                          ? 'border-blue-500 bg-blue-900/20'
                          : 'border-gray-700 hover:border-gray-600'
                        }`}
                      onClick={() => setSelectedLog(selectedLog === log.id ? null : log.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="text-2xl">{getStatusIcon(log.status)}</span>
                            <div>
                              <h3 className="font-bold text-white text-lg">
                                {log.api_name}
                              </h3>
                              <p className="text-sm text-gray-400">
                                {formatDate(log.started_at)}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-4 text-sm">
                            <span className={`font-semibold ${getStatusColor(log.status)}`}>
                              {log.status.toUpperCase()}
                            </span>
                            {log.source && (
                              <span className="text-gray-400">
                                Fuente: <span className="text-blue-400">{log.source}</span>
                              </span>
                            )}
                          </div>

                          {log.total_items && (
                            <div className="mt-3">
                              <div className="flex justify-between text-sm text-gray-400 mb-1">
                                <span>
                                  {log.processed_items}/{log.total_items} items
                                </span>
                                <span>{getLogProgress(log)}%</span>
                              </div>
                              <div className="w-full bg-gray-700 rounded-full h-1.5">
                                <div
                                  className={`h-1.5 rounded-full ${log.status === 'success' ? 'bg-green-600' :
                                      log.status === 'error' ? 'bg-red-600' :
                                        log.status === 'running' ? 'bg-blue-600' : 'bg-yellow-600'
                                    }`}
                                  style={{ width: `${getLogProgress(log)}%` }}
                                />
                              </div>
                            </div>
                          )}

                          {selectedLog === log.id && (
                            <div className="mt-4 pt-4 border-t border-gray-700">
                              <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                  <span className="text-gray-400">Endpoint:</span>
                                  <p className="text-white font-mono text-xs mt-1">{log.endpoint}</p>
                                </div>
                                <div>
                                  <span className="text-gray-400">Errores:</span>
                                  <p className="text-white mt-1">{log.error_count}</p>
                                </div>
                                {log.message && (
                                  <div className="col-span-2">
                                    <span className="text-gray-400">Mensaje:</span>
                                    <p className="text-white mt-1">{log.message}</p>
                                  </div>
                                )}
                                {log.error_details && (
                                  <div className="col-span-2">
                                    <span className="text-red-400">Detalles del Error:</span>
                                    <p className="text-red-300 font-mono text-xs mt-1 bg-red-900/20 p-2 rounded">
                                      {log.error_details}
                                    </p>
                                  </div>
                                )}
                                {log.completed_at && (
                                  <div className="col-span-2">
                                    <span className="text-gray-400">Completado:</span>
                                    <p className="text-white mt-1">{formatDate(log.completed_at)}</p>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>

                        <button className="text-gray-400 hover:text-white transition-colors">
                          {selectedLog === log.id ? '▲' : '▼'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Stats Tab */}
        {activeTab === 'stats' && stats && (
          <div className="fade-in">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="card bg-gradient-to-br from-purple-900/40 to-purple-700/20">
                <div className="text-5xl mb-3">🐉</div>
                <h3 className="text-lg text-gray-300 mb-1">Criaturas</h3>
                <p className="text-4xl font-bold text-white">{stats.creatures}</p>
              </div>

              <div className="card bg-gradient-to-br from-blue-900/40 to-blue-700/20">
                <div className="text-5xl mb-3">⚔️</div>
                <h3 className="text-lg text-gray-300 mb-1">Items</h3>
                <p className="text-4xl font-bold text-white">{stats.items}</p>
              </div>

              <div className="card bg-gradient-to-br from-green-900/40 to-green-700/20">
                <div className="text-5xl mb-3">🗺️</div>
                <h3 className="text-lg text-gray-300 mb-1">Zonas de Hunt</h3>
                <p className="text-4xl font-bold text-white">{stats.hunting_places}</p>
              </div>

              <div className="card bg-gradient-to-br from-yellow-900/40 to-yellow-700/20">
                <div className="text-5xl mb-3">📜</div>
                <h3 className="text-lg text-gray-300 mb-1">Quests</h3>
                <p className="text-4xl font-bold text-white">{stats.quests}</p>
              </div>

              <div className="card bg-gradient-to-br from-cyan-900/40 to-cyan-700/20">
                <div className="text-5xl mb-3">📋</div>
                <h3 className="text-lg text-gray-300 mb-1">Sincronizaciones</h3>
                <p className="text-4xl font-bold text-white">{stats.sync_logs}</p>
              </div>

              <div className="card bg-gradient-to-br from-pink-900/40 to-pink-700/20">
                <div className="text-5xl mb-3">📈</div>
                <h3 className="text-lg text-gray-300 mb-1">Total de Datos</h3>
                <p className="text-4xl font-bold text-white">
                  {stats.creatures + stats.items + stats.hunting_places + stats.quests}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Conflict Modal */}
        {showConflictModal && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-900 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border-2 border-yellow-500/50">
              <div className="p-6">
                <h2 className="text-2xl font-bold text-white mb-4">
                  ⚠️ Conflictos Detectados
                </h2>
                <p className="text-gray-300 mb-6">
                  Se encontraron {conflicts.length} elementos con datos diferentes.
                  Revisa los cambios y decide qué hacer:
                </p>

                <div className="space-y-4 mb-6">
                  {conflicts.slice(0, 5).map((conflict, idx) => (
                    <div key={idx} className="border border-yellow-500/30 rounded-lg p-4 bg-yellow-900/10">
                      <h3 className="font-bold text-white mb-2">{conflict.item_name}</h3>
                      <div className="space-y-2">
                        {conflict.conflicts.map((comp, cIdx) => (
                          comp.different && (
                            <div key={cIdx} className="text-sm grid grid-cols-3 gap-2">
                              <span className="text-gray-400">{comp.field}:</span>
                              <span className="text-red-400">
                                {JSON.stringify(comp.old_value)}
                              </span>
                              <span className="text-green-400">
                                → {JSON.stringify(comp.new_value)}
                              </span>
                            </div>
                          )
                        ))}
                      </div>
                    </div>
                  ))}
                  {conflicts.length > 5 && (
                    <p className="text-gray-400 text-sm text-center">
                      ... y {conflicts.length - 5} más
                    </p>
                  )}
                </div>

                <div className="flex gap-4">
                  <button
                    onClick={() => resolveConflicts('skip_all')}
                    disabled={loading}
                    className="flex-1 px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-xl font-semibold transition-all"
                  >
                    ⏭️ Omitir Todos
                  </button>
                  <button
                    onClick={() => resolveConflicts('overwrite_all')}
                    disabled={loading}
                    className="flex-1 px-6 py-3 bg-yellow-600 hover:bg-yellow-500 text-white rounded-xl font-semibold transition-all"
                  >
                    ✏️ Sobrescribir Todos
                  </button>
                  <button
                    onClick={() => setShowConflictModal(false)}
                    className="px-6 py-3 bg-red-600 hover:bg-red-500 text-white rounded-xl font-semibold transition-all"
                  >
                    ✖️ Cancelar
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DataSyncPanel;
