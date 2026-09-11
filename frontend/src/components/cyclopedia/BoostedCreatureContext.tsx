import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { creaturesApi, tibiaApi } from '../../services/api';
import type {
  BoostedCreatureProjection,
  CreatureSimple,
  TibiaBoostedResponse,
} from '../../types';

interface BoostedCreatureContextValue {
  response: TibiaBoostedResponse | null;
  featuredCreature: CreatureSimple | null;
  featuredBoss: CreatureSimple | null;
  isBoosted: (creature: CreatureSimple) => boolean;
}

const BoostedCreatureContext = createContext<BoostedCreatureContextValue | null>(null);

function projectionFallback(
  projection: BoostedCreatureProjection,
  isBoss: boolean,
): CreatureSimple | null {
  if (
    projection.resolution_state !== 'resolved'
    || projection.id == null
    || !projection.name
  ) {
    return null;
  }

  return {
    id: projection.id,
    slug: projection.slug || undefined,
    name: projection.name,
    hitpoints: null,
    experience: null,
    is_boss: isBoss,
  };
}

async function resolveProjection(
  projection: BoostedCreatureProjection,
  isBoss: boolean,
): Promise<CreatureSimple | null> {
  const fallback = projectionFallback(projection, isBoss);
  if (!fallback) return null;

  try {
    return await creaturesApi.getById(fallback.id);
  } catch {
    // The authoritative boosted projection is already canonically resolved.
    // Keep it usable even if the richer creature detail request is unavailable.
    return fallback;
  }
}

export function BoostedCreatureProvider({ children }: { children: React.ReactNode }) {
  const [response, setResponse] = useState<TibiaBoostedResponse | null>(null);
  const [featuredCreature, setFeaturedCreature] = useState<CreatureSimple | null>(null);
  const [featuredBoss, setFeaturedBoss] = useState<CreatureSimple | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    void tibiaApi
      .getBoosted(controller.signal)
      .then(async (boosted) => {
        if (!active || controller.signal.aborted) return;
        setResponse(boosted);

        const [creature, boss] = await Promise.all([
          resolveProjection(boosted.creature, false),
          resolveProjection(boosted.boss, true),
        ]);

        if (!active || controller.signal.aborted) return;
        setFeaturedCreature(creature);
        setFeaturedBoss(boss);
      })
      .catch(() => {
        if (!active || controller.signal.aborted) return;
        setResponse(null);
        setFeaturedCreature(null);
        setFeaturedBoss(null);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  const value = useMemo<BoostedCreatureContextValue>(() => ({
    response,
    featuredCreature,
    featuredBoss,
    isBoosted: (creature) => {
      const projection = creature.is_boss ? response?.boss : response?.creature;
      return projection?.resolution_state === 'resolved'
        && projection.id === creature.id;
    },
  }), [featuredBoss, featuredCreature, response]);

  return (
    <BoostedCreatureContext.Provider value={value}>
      {children}
    </BoostedCreatureContext.Provider>
  );
}

export function useBoostedCreature(): BoostedCreatureContextValue | null {
  return useContext(BoostedCreatureContext);
}
