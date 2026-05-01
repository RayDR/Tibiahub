// AdminDashboard.tsx - Component for Admin Dashboard
import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface TibiaApiStatus {
  status: 'online' | 'offline' | 'degraded';
  latency_ms?: number;
  cached: boolean;
  last_check: string;
  message: string;
}

interface UserCharacter {
  character_name: string;
  level?: number;
  vocation?: string;
  last_seen?: string;
}

interface User {
  id: number;
  username: string;
  email?: string;
  guild_rank?: string;
  is_active: boolean;
  is_superuser: boolean;
  join_date?: string;
  created_at: string;
  characters: UserCharacter[];
}

interface SystemStats {
  total_users: number;
  active_users: number;
  inactive_users: number;
  admin_users: number;
  total_characters_linked: number;
  guild_ranks: Array<{ rank: string; count: number }>;
}

interface SystemSettings {
  tibia_validation_enabled: boolean;
  tibia_validation_strict: boolean;
  access_token_expire_minutes: number;
}

export default function AdminDashboard() {
  const [tibiaApiStatus, setTibiaApiStatus] = useState<TibiaApiStatus | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAdminData();
    // Refresh every 30 seconds
    const interval = setInterval(fetchAdminData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchAdminData = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) {
        setError('No authentication token found');
        return;
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      // Fetch all data in parallel
      const [statusRes, usersRes, statsRes, settingsRes] = await Promise.all([
        fetch('/api/v1/admin-secret/tibia-api-status', { headers }),
        fetch('/api/v1/admin-secret/users', { headers }),
        fetch('/api/v1/admin-secret/stats', { headers }),
        fetch('/api/v1/admin-secret/settings', { headers })
      ]);

      if (!statusRes.ok || !usersRes.ok || !statsRes.ok || !settingsRes.ok) {
        throw new Error('Failed to fetch admin data');
      }

      setTibiaApiStatus(await statusRes.json());
      setUsers(await usersRes.json());
      setStats(await statsRes.json());
      setSettings(await settingsRes.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const toggleValidationStrict = async (checked: boolean) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/admin-secret/settings', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ tibia_validation_strict: checked })
      });

      if (!response.ok) throw new Error('Failed to update settings');
      
      const updatedSettings = await response.json();
      setSettings(updatedSettings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update settings');
    }
  };

  const toggleValidationEnabled = async (checked: boolean) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/admin-secret/settings', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ tibia_validation_enabled: checked })
      });

      if (!response.ok) throw new Error('Failed to update settings');
      
      const updatedSettings = await response.json();
      setSettings(updatedSettings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update settings');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'bg-green-500';
      case 'offline': return 'bg-red-500';
      case 'degraded': return 'bg-yellow-500';
      default: return 'bg-gray-500';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p>Loading admin dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <h1 className="text-3xl font-bold mb-6">Admin Dashboard</h1>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Tibia API Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Tibia API Status</span>
            {tibiaApiStatus && (
              <Badge className={getStatusColor(tibiaApiStatus.status)}>
                {tibiaApiStatus.status.toUpperCase()}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {tibiaApiStatus && (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">{tibiaApiStatus.message}</p>
              {tibiaApiStatus.latency_ms && (
                <p className="text-sm">Latency: <span className="font-semibold">{tibiaApiStatus.latency_ms}ms</span></p>
              )}
              <p className="text-xs text-muted-foreground">
                Last checked: {new Date(tibiaApiStatus.last_check).toLocaleString()}
                {tibiaApiStatus.cached && ' (cached)'}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* System Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_users || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.active_users || 0} active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Admin Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.admin_users || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Characters Linked</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_characters_linked || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Guild Ranks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {stats?.guild_ranks.map(rank => (
                <div key={rank.rank} className="text-xs flex justify-between">
                  <span>{rank.rank}</span>
                  <span className="font-semibold">{rank.count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Validation Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Validation Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Tibia Character Validation</p>
              <p className="text-sm text-muted-foreground">
                Validate character names using Tibia API during registration
              </p>
            </div>
            <Switch
              checked={settings?.tibia_validation_enabled || false}
              onCheckedChange={toggleValidationEnabled}
            />
          </div>

          {settings?.tibia_validation_enabled && (
            <div className="flex items-center justify-between pl-4 border-l-2">
              <div>
                <p className="font-medium">Strict Mode</p>
                <p className="text-sm text-muted-foreground">
                  Block registration when Tibia API is down
                </p>
              </div>
              <Switch
                checked={settings?.tibia_validation_strict || false}
                onCheckedChange={toggleValidationStrict}
              />
            </div>
          )}

          {tibiaApiStatus?.status === 'offline' && settings?.tibia_validation_strict && (
            <Alert>
              <AlertDescription>
                ⚠️ Tibia API is offline and strict mode is enabled. Users cannot register with characters.
                Consider disabling strict mode temporarily.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Users List */}
      <Card>
        <CardHeader>
          <CardTitle>Users ({users.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">ID</th>
                  <th className="text-left p-2">Username</th>
                  <th className="text-left p-2">Email</th>
                  <th className="text-left p-2">Rank</th>
                  <th className="text-left p-2">Status</th>
                  <th className="text-left p-2">Characters</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.id} className="border-b hover:bg-muted/50">
                    <td className="p-2">{user.id}</td>
                    <td className="p-2">
                      <div className="flex items-center gap-2">
                        {user.username}
                        {user.is_superuser && (
                          <Badge variant="destructive" className="text-xs">Admin</Badge>
                        )}
                      </div>
                    </td>
                    <td className="p-2 text-sm text-muted-foreground">
                      {user.email || 'N/A'}
                    </td>
                    <td className="p-2">
                      <Badge variant="outline">{user.guild_rank || 'No Rank'}</Badge>
                    </td>
                    <td className="p-2">
                      <Badge variant={user.is_active ? 'default' : 'secondary'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="p-2">
                      {user.characters.length > 0 ? (
                        <div className="space-y-1">
                          {user.characters.map(char => (
                            <div key={char.character_name} className="text-sm">
                              <span className="font-medium">{char.character_name}</span>
                              {char.level && (
                                <span className="text-muted-foreground">
                                  {' '}• Lv {char.level}
                                </span>
                              )}
                              {char.vocation && (
                                <span className="text-muted-foreground">
                                  {' '}• {char.vocation}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground">No characters</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
