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
import ItemPreviewPanel from './ItemPreviewPanel';

type PreviewKind = 'creature' | 'boss' | 'item';

type PreviewSelection =
  | { kind: 'creature' | 'boss'; creatureId: number }
  | { kind: 'item'; identifier: string };

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
  const [selectedItemIdentifier, setSelectedItemIdentifier] = useState<string | null>(null);
  const tab = new URLSearchParams(location.search).get('tab') || 'creatures';

  useEffect(() => {
    resetCreatureSelection?.(null);
    setSelectedItemIdentifier(null);
  }, [location.search, resetCreatureSelection]);

  useEffect(() => {
    if (tab !== 'items') return undefined;

    const root = document.querySelector<HTMLElement>(
      '.app-shell-cyclopedia main[data-workspace-main="cyclopedia"]',
    );
    if (!root) return undefined;

    const markItemCards = () => {
      const cards = root.querySelectorAll<HTMLElement>('article[data-cyclopedia-result]');
      cards.forEach((card) => {
        const itemLink = card.querySelector<HTMLAnchorElement>('a[href^="/items/"]');
        if (!itemLink) return;
        const identifier = decodeURIComponent(itemLink.pathname.replace(/^\/items\//, '').replace(/\/$/, ''));
        if (!identifier) return;
        card.dataset.cyclopediaItemCard = 'true';
        card.dataset.itemIdentifier = identifier;
        card.setAttribute('role', 'button');
        card.tabIndex = 0;
      });
    };

    const observer = new MutationObserver(markItemCards);
    markItemCards();
    observer.observe(root, { childList: true, subtree: true });

    const selectCard = (card: HTMLElement) => {
      const identifier = card.dataset.itemIdentifier;
      if (identifier) setSelectedItemIdentifier(identifier);
    };

    const onClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const card = target.closest<HTMLElement>('article[data-cyclopedia-item-card="true"]');
      if (!card || !root.contains(card)) return;
      if (target.closest('a, button, input, select, textarea')) return;
      selectCard(card);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (!target.matches('article[data-cyclopedia-item-card="true"]')) return;
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      selectCard(target);
    };

    root.addEventListener('click', onClick);
    root.addEventListener('keydown', onKeyDown);

    return () => {
      observer.disconnect();
      root.removeEventListener('click', onClick);
      root.removeEventListener('keydown', onKeyDown);
      root.querySelectorAll<HTMLElement>('article[data-cyclopedia-item-card="true"]').forEach((card) => {
        delete card.dataset.cyclopediaItemCard;
        delete card.dataset.itemIdentifier;
        delete card.dataset.selected;
        card.removeAttribute('role');
        card.removeAttribute('aria-pressed');
        card.removeAttribute('tabindex');
      });
    };
  }, [tab]);

  useLayoutEffect(() => {
    const cards = document.querySelectorAll<HTMLElement>('article[data-cyclopedia-item-card="true"]');
    cards.forEach((card) => {
      const selected = tab === 'items' && selectedItemIdentifier != null && card.dataset.itemIdentifier === selectedItemIdentifier;
      card.dataset.selected = selected ? 'true' : 'false';
      card.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
  }, [selectedItemIdentifier, tab]);

  let selection: PreviewSelection | null = null;
  if ((tab === 'creatures' || tab === 'bosses') && browser?.selectedCreatureId != null) {
    selection = {
      kind: tab === 'bosses' ? 'boss' : 'creature',
      creatureId: browser.selectedCreatureId,
    };
  } else if (tab === 'items' && selectedItemIdentifier) {
    selection = { kind: 'item', identifier: selectedItemIdentifier };
  }

  const closePreview = () => {
    browser?.selectCreature(null);
    setSelectedItemIdentifier(null);
  };

  return (
    <div className="cyclopedia-reference-frame">
      <main className="relative min-h-0 min-w-0 flex-1" data-workspace-main="cyclopedia">
        <Container>{children}</Container>
      </main>
      {selection ? (
        <CyclopediaPreviewPortal
          selection={selection}
          onClose={closePreview}
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

function selectedCardFor(selection: PreviewSelection): HTMLElement | null {
  if (selection.kind === 'item') {
    return Array.from(
      document.querySelectorAll<HTMLElement>('article[data-cyclopedia-item-card="true"]'),
    ).find((card) => card.dataset.itemIdentifier === selection.identifier) || null;
  }

  return document.querySelector<HTMLElement>(
    '[data-creature-card][data-selected="true"]',
  );
}

function CyclopediaPreviewPortal({
  selection,
  onClose,
}: {
  selection: PreviewSelection;
  onClose: () => void;
}) {
  const dockRef = useRef<HTMLElement | null>(null);
  const [resultsRegion, setResultsRegion] = useState<HTMLElement | null>(null);
  const [insets, setInsets] = useState<PreviewInsets>({ top: 0, bottom: PREVIEW_EDGE_GAP });
  const selectionKey = selection.kind === 'item'
    ? `item:${selection.identifier}`
    : `${selection.kind}:${selection.creatureId}`;

  useLayoutEffect(() => {
    const selectedCard = selectedCardFor(selection);
    const result = selectedCard?.closest<HTMLElement>('[data-cyclopedia-result]');
    const grid = result?.parentElement;
    const region = grid?.parentElement;

    if (!region) {
      setResultsRegion(null);
      return undefined;
    }

    region.dataset.cyclopediaPreviewHost = 'true';
    region.dataset.cyclopediaPreviewKind = selection.kind;
    setResultsRegion(region);

    return () => {
      delete region.dataset.cyclopediaPreviewHost;
      delete region.dataset.cyclopediaPreviewKind;
    };
  }, [selectionKey]);

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

      const nextTop = Math.max(
        PREVIEW_EDGE_GAP,
        Math.min(window.innerHeight - PREVIEW_EDGE_GAP, Math.max(regionRect.top, controlsBottom)),
      );

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

  const label = selection.kind === 'boss' ? 'boss' : selection.kind === 'item' ? 'item' : 'creature';
  const dockStyle = {
    '--cyclopedia-preview-top': `${insets.top}px`,
    '--cyclopedia-preview-bottom': `${insets.bottom}px`,
  } as CSSProperties;

  return createPortal(
    <aside
      ref={dockRef}
      className="cyclopedia-creature-preview-dock"
      aria-label={`Selected ${label} preview`}
      data-preview-kind={selection.kind}
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
        {selection.kind === 'item' ? (
          <ItemPreviewPanel identifier={selection.identifier} />
        ) : (
          <CreaturePreviewPanel creatureId={selection.creatureId} kind={selection.kind} />
        )}
      </div>
    </aside>,
    document.body,
  );
}
