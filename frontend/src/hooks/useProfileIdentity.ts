import { useCallback, useEffect, useState } from 'react';
import { OwnershipClaim, ProfileIdentity, profileApi } from '../services/profile';

export function useProfileIdentity() {
  const [profile, setProfile] = useState<ProfileIdentity | null>(null);
  const [claims, setClaims] = useState<OwnershipClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const reload = useCallback(async () => {
    setLoading(true); setError(false);
    try {
      const [identity, own, incoming] = await Promise.all([
        profileApi.me(), profileApi.claims(), profileApi.incomingClaims(),
      ]);
      setProfile(identity); setClaims([...incoming.map(row => ({ ...row, incoming: true })), ...own]);
    } catch { setError(true); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void reload(); }, [reload]);
  return { profile, setProfile, claims, setClaims, loading, error, reload };
}
