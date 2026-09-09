import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

export type CyclopediaPreviewSelection =
  | { kind: 'item'; identifier: string }
  | { kind: 'quest'; identifier: string }
  | null;

interface CyclopediaPreviewSelectionContextValue {
  selection: CyclopediaPreviewSelection;
  select: (selection: Exclude<CyclopediaPreviewSelection, null>) => void;
  clear: () => void;
}

const CyclopediaPreviewSelectionContext = createContext<CyclopediaPreviewSelectionContextValue | null>(null);

export function CyclopediaPreviewSelectionProvider({ children }: { children: React.ReactNode }) {
  const [selection, setSelection] = useState<CyclopediaPreviewSelection>(null);
  const select = useCallback((next: Exclude<CyclopediaPreviewSelection, null>) => setSelection(next), []);
  const clear = useCallback(() => setSelection(null), []);
  const value = useMemo(() => ({ selection, select, clear }), [clear, select, selection]);

  return (
    <CyclopediaPreviewSelectionContext.Provider value={value}>
      {children}
    </CyclopediaPreviewSelectionContext.Provider>
  );
}

export function useCyclopediaPreviewSelection(): CyclopediaPreviewSelectionContextValue {
  const context = useContext(CyclopediaPreviewSelectionContext);
  if (!context) throw new Error('useCyclopediaPreviewSelection must be used within CyclopediaPreviewSelectionProvider');
  return context;
}
