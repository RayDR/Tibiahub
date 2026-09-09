import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react';
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

interface PreviewInsets {
  top: number;
  bottom: number;
}

const PREVIEW_EDGE_GAP = 16;

function CyclopediaPreviewPortal({
  creatureId,
  kind,
  onClose,
}: {
  creatureId: number;
  kind: 'creature' | 'boss';
  onClose: () => void;
}) {
  const dockRef = useRef<HTMLElement | null>(null);
  const [resultsRegion, setResultsRegion] = useState<HTMLElement | null>(null);
  const [insets, setInsets] = useState<PreviewInsets>({ top: 0, bottom: PREVIEW_EDGE_GAP });

  useLayoutEffect(() => {
    const selectedCard = document.querySelector<HTMLElement>(
      '[data-creature-card][data-selected="true"]',
    );
    const result = selectedCard?.closest<HTMLElement>('[data-cyclopedia-result]');
    const grid = result?.parentElement;
    const region = grid?.parentElement;

    if (!region) {
      setResultsRegion(null);
      return undefined;
    }

    region.dataset.cyclopediaPreviewHost = 'true';
    setResultsRegion(region);

    return () => {
      delete region.dataset.cyclopediaPreviewHost;
    };
  }, [creatureId]);

  useLayoutEffect(() => {
    if (!resultsRegion) return undefined;

    let frame = 0;
    let searchObserver: MutationObserver | null = null;
    let resizeObserver: ResizeObserver | null = null;

    const measure = () => {
      frame = 0;

      const regionRect = resultsRegion.getBoundingClientRect();
      const nav = document.querySelector<HTMLElement>(
        '.app-shell-cyclopedia header.app-primary-nav',
      );
      const tabs = document.querySelector<HTMLElement>(
        '.app-tablist[data-variant="cyclopedia"]',
      );
      const searchSurface = tabs?.closest<HTMLElement>('article');

      const navBottom = nav?.getBoundingClientRect().bottom ?? 0;
      const searchBottom = searchSurface?.getBoundingClientRect().bottom ?? 0;
      const controlsBottom = Math.max(navBottom, searchBottom) + PREVIEW_EDGE_GAP;

      // At the top of the page the preview starts exactly with the results
      // region. Once that region scrolls under the application controls, it
      // becomes a viewport dock immediately below the sticky search surface.
      const nextTop = Math.max(
        PREVIEW_EDGE_GAP,
        Math.min(window.innerHeight - PREVIEW_EDGE_GAP, Math.max(regionRect.top, controlsBottom)),
      );

      // Keep the preview spatially owned by the results region near its end so
      // it cannot float across the footer after the result set is exhausted.
      const nextBottom = Math.max(
        PREVIEW_EDGE_GAP,
        window.innerHeight - regionRect.bottom + PREVIEW_EDGE_GAP,
      );

      setInsets((current) =>
        Math.abs(current.top - nextTop) < 1 && Math.abs(current.bottom - nextBottom) < 1
          ? current
          : { top: nextTop, bottom: nextBottom },
      );
    };

    const scheduleMeasure = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(measure);
    };

    scheduleMeasure();
    window.addEventListener('scroll', scheduleMeasure, { passive: true });
    window.addEventListener('resize', scheduleMeasure);

    const tabs = document.querySelector<HTMLElement>(
      '.app-tablist[data-variant="cyclopedia"]',
    );
    const searchSurface = tabs?.closest<HTMLElement>('article');
    const stickyShell = searchSurface?.parentElement;

    if (stickyShell) {
      searchObserver = new MutationObserver(scheduleMeasure);
      searchObserver.observe(stickyShell, {
        attributes: true,
        attributeFilter: ['class', 'style'],
      });
    }

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(scheduleMeasure);
      resizeObserver.observe(resultsRegion);
      if (searchSurface) resizeObserver.observe(searchSurface);
    }

    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', scheduleMeasure);
      window.removeEventListener('resize', scheduleMeasure);
      searchObserver?.disconnect();
      resizeObserver?.disconnect();
    };
  }, [resultsRegion]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  if (!resultsRegion) return null;

  const label = kind === 'boss' ? 'boss' : 'creature';
  const dockStyle = {
    '--cyclopedia-preview-top': `${insets.top}px`,
    '--cyclopedia-preview-bottom': `${insets.bottom}px`,
  } as CSSProperties;

  return createPortal(
    <aside
      ref={dockRef}
      className="cyclopedia-creature-preview-dock"
      aria-label={`Selected ${label} preview`}
      data-preview-kind={kind}
      style={dockStyle}
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
    </aside>,
    document.body,
  );
}
