import { useCallback } from 'react';
import { useOutletContext } from 'react-router-dom';

import { GuildManagementCapability } from '../services/guildManagement';
import { GuildLayoutContext } from '../utils/guildContext';

const normalizeGuild = (value: string) => value.trim().toLocaleLowerCase();

export function useGuildCapability(capability: GuildManagementCapability) {
  const context = useOutletContext<GuildLayoutContext>();
  const authorized = Boolean(context?.guildContext.capabilities[capability]);
  const canManageGuild = useCallback((guildName?: string | null) => Boolean(
    authorized
    && guildName
    && normalizeGuild(guildName) === normalizeGuild(context.selectedGuild)
  ), [authorized, context?.selectedGuild]);

  return {
    authorizedGuilds: authorized ? [context.selectedGuild] : [],
    canManageGuild,
    loadingCapabilities: false,
  };
}
