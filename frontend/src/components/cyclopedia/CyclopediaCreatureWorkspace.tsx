import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';

import { Container } from '../ui';
import { CreatureBrowserProvider, useCreatureBrowser } from './CreatureBrowserContext';
import CreaturePreviewPanel from './CreaturePreviewPanel';

export default function CyclopediaCreatureWorkspace({ children }: { children: ReactNode }) {
  return (
    <CreatureBrowserProvider>
      <CyclopediaCreatureWorkspaceInner>{children}</CyclopediaCreatureWorkspaceInner>
    </CreatureBrowserProvider>
  );
}

function CyclopediaCreatureWorkspaceInner({ children }: { children: ReactNode }) {
  const location = useLocation();
  const browser = useCreatureBrowser();
  const resetCreatureSelection = browser?.selectCreature;
  const tab = new URLSearchParams(location.search).get('tab') || 'creatures';
  const supportsPreview = tab === 'creatures' || tab === 'bosses';
  const showPreview = supportsPreview && browser?.selectedCreatureId != null;

  useEffect(() => {
    resetCreatureSelection?.(null);
  }, [location.search, resetCreatureSelection]);

  return (
    <div className="cyclopedia-reference-frame">
      <main className="relative min-h-0 min-w-0 flex-1" data-workspace-main="cyclopedia">
        <Container>{children}</Container>
      </main>
      {showPreview && browser?.selectedCreatureId != null ? (
        <CyclopediaPreviewPortal
          creatureId={browser.selectedCreatureId}
          kind={tab === 'bosses' ? 'boss' : 'creature'}
          onClose={() => browser.selectCreature(null)}
        />
      ) : null}
    </div>
  );
}

function CyclopediaPreviewPortal({
  creatureId,
  kind,
  onClose,
}: {
  creatureId: number;
  kind: 'creature' | 'boss';
  onClose: () => void;
}) {
  const [host, setHost] = useState<HTMLElement | null>(null);
  const dockRef = useRef<HTMLElement | null>(null);

  useLayoutEffect(() => {
    const selectedCard = document.querySelector<HTMLElement>('[data-creature-card][data-selected="true"]');
    const result = selectedCard?.closest<HTMLElement>('[data-cyclopedia-result]');
    const grid = result?.parentElement;
    const resultsRegion = grid?.parentElement;

    if (!resultsRegion) {
      setHost(null);
      return undefined;
    }

    resultsRegion.dataset.cyclopediaPreviewHost = 'true';
    setHost(resultsRegion);

    return () => {
      delete resultsRegion.dataset.cyclopediaPreviewHost;
    };
  }, [creatureId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (dockRef.current?.contains(target)) return;
      if (target.closest('[data-creature-card]')) return;
      onClose();
    };

    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown);
    };
  }, [onClose]);

  if (!host) return null;

  const label = kind === 'boss' ? 'boss' : 'creature';

  return createPortal(
    <>
      <button
        type="button"
        className="cyclopedia-creature-preview-backdrop"
        onClick={onClose}
        aria-label={`Close selected ${label} preview`}
      />
      <aside
        ref={dockRef}
        className="cyclopedia-creature-preview-dock"
        aria-label={`Selected ${label} preview`}
        data-preview-kind={kind}
      >
        <div className="cyclopedia-creature-preview-sticky">
          <button
            type="button"
            className="cyclopedia-creature-preview-close"
            onClick={onClose}
            aria-label={`Close selected ${label} preview`}
            title="Close preview"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
          <CreaturePreviewPanel creatureId={creatureId} kind={kind} />
        </div>
      </aside>
    </>,
    host,
  );
}
