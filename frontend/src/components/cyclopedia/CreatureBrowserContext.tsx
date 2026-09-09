import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

import { creatureBrowserApi, type CreatureBrowseItem } from '../../services/creatureBrowser';

interface CreatureBrowserContextValue {
  selectedCreatureId: number | null;
  selectCreature: (id: number | null) => void;
  registerCreature: (id: number) => void;
  browseItem: (id: number) => CreatureBrowseItem | undefined;
}

const CreatureBrowserContext = createContext<CreatureBrowserContextValue | null>(null);

export function CreatureBrowserProvider({ children }: { children: React.ReactNode }) {
  const [selectedCreatureId, setSelectedCreatureId] = useState<number | null>(null);
  const [items, setItems] = useState<Map<number, CreatureBrowseItem>>(() => new Map());
  const pendingRef = useRef(new Set<number>());
  const timerRef = useRef<number | null>(null);
  const requestRef = useRef<AbortController | null>(null);

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    requestRef.current?.abort();
  }, []);

  const flush = useCallback(() => {
    timerRef.current = null;
    const ids = [...pendingRef.current].slice(0, 60);
    ids.forEach((id) => pendingRef.current.delete(id));
    if (ids.length === 0) return;

    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    void creatureBrowserApi.getItems(ids, controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) return;
        setItems((current) => {
          const next = new Map(current);
          rows.forEach((row) => next.set(row.id, row));
          return next;
        });
      })
      .catch((error: any) => {
        if (error?.name !== 'CanceledError' && error?.code !== 'ERR_CANCELED') {
          console.error('Failed to enrich creature cards', error);
        }
      })
      .finally(() => {
        if (requestRef.current === controller) requestRef.current = null;
        if (pendingRef.current.size > 0 && timerRef.current === null) {
          timerRef.current = window.setTimeout(flush, 40);
        }
      });
  }, []);

  const registerCreature = useCallback((id: number) => {
    if (items.has(id) || pendingRef.current.has(id)) return;
    pendingRef.current.add(id);
    if (timerRef.current === null) timerRef.current = window.setTimeout(flush, 35);
  }, [flush, items]);

  const browseItem = useCallback((id: number) => items.get(id), [items]);

  return (
    <CreatureBrowserContext.Provider value={{
      selectedCreatureId,
      selectCreature: setSelectedCreatureId,
      registerCreature,
      browseItem,
    }}>
      {children}
    </CreatureBrowserContext.Provider>
  );
}

export function useCreatureBrowser(): CreatureBrowserContextValue | null {
  return useContext(CreatureBrowserContext);
}
