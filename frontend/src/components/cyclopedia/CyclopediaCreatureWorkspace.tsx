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
import {
  CyclopediaPreviewSelectionProvider,
  useCyclopediaPreviewSelection,
} from './CyclopediaPreviewSelectionContext';
import CreaturePreviewPanel from './CreaturePreviewPanel';
import HuntZonePreviewPanel from './HuntZonePreviewPanel';
import ItemPreviewPanel from './ItemPreviewPanel';
import NpcPreviewPanel from './NpcPreviewPanel';
import QuestPreviewPanel from './QuestPreviewPanel';

type PreviewSelection =
  | { kind: 'creature'; creatureId: number }
  | { kind: 'boss'; creatureId: number }
  | { kind: 'item'; identifier: string }
  | { kind: 'quest'; identifier: string }
  | { kind: 'zone'; identifier: string }
  | { kind: 'npc'; identifier: string };

export default function CyclopediaCreatureWorkspace({ children }: { children: ReactNode }) {
  return (
    <CreatureBrowserProvider>
      <CyclopediaPreviewSelectionProvider>
        <CyclopediaCreatureWorkspaceInner>{children}</CyclopediaCreatureWorkspaceInner>
      </CyclopediaPreviewSelectionProvider>
    </CreatureBrowserProvider>
  );
}

function CyclopediaCreatureWorkspaceInner({ children }: { children: ReactNode }) {
  const location = useLocation();
  const browser = useCreatureBrowser();
  const genericPreview = useCyclopediaPreviewSelection();
  const resetCreatureSelection = browser?.selectCreature;
  const clearGenericPreview = genericPreview.clear;
  const genericSelection = genericPreview.selection;
  const tab = new URLSearchParams(location.search).get('tab') || 'creatures';
  // Canonical URL key is `loot`; keep `items` as a compatibility alias for
  // older links while the page mode itself remains `items` internally.
  const isLootTab = tab === 'loot' || tab === 'items';

  useEffect(() => {
    resetCreatureSelection?.(null);
    clearGenericPreview();
  }, [clearGenericPreview, location.search, resetCreatureSelection]);

  let selection: PreviewSelection | null = null;
  if ((tab === 'creatures' || tab === 'bosses') && browser?.selectedCreatureId != null) {
    selection = tab === 'bosses'
      ? { kind: 'boss', creatureId: browser.selectedCreatureId }
      : { kind: 'creature', creatureId: browser.selectedCreatureId };
  } else if (isLootTab && genericSelection?.kind === 'item') {
    selection = genericSelection;
  } else if (tab === 'quests' && genericSelection?.kind === 'quest') {
    selection = genericSelection;
  } else if (tab === 'zones' && genericSelection?.kind === 'zone') {
    selection = genericSelection;
  } else if (tab === 'npcs' && genericSelection?.kind === 'npc') {
    selection = genericSelection;
  }

  const closePreview = () => {
    browser?.selectCreature(null);
    clearGenericPreview();
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

  if (selection.kind === 'quest') {
    return Array.from(
      document.querySelectorAll<HTMLElement>('article[data-cyclopedia-quest-card="true"]'),
    ).find((card) => card.dataset.questIdentifier === selection.identifier) || null;
  }

  if (selection.kind === 'zone') {
    return Array.from(
      document.querySelectorAll<HTMLElement>('article[data-cyclopedia-zone-card="true"]'),
    ).find((card) => card.dataset.zoneIdentifier === selection.identifier) || null;
  }

  if (selection.kind === 'npc') {
    return Array.from(
      document.querySelectorAll<HTMLElement>('article[data-cyclopedia-npc-card="true"]'),
    ).find((card) => card.dataset.npcIdentifier === selection.identifier) || null;
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
  const selectionKey = selection.kind === 'creature' || selection.kind === 'boss'
    ? `${selection.kind}:${selection.creatureId}`
    : `${selection.kind}:${selection.identifier}`;

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
  }, [selectionKey]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const label = selection.kind === 'boss'
    ? 'boss'
    : selection.kind === 'item'
      ? 'item'
      : selection.kind === 'quest'
        ? 'quest'
        : selection.kind === 'zone'
          ? 'hunt zone'
          : selection.kind === 'npc'
            ? 'npc'
            : 'creature';
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
        ) : selection.kind === 'quest' ? (
          <QuestPreviewPanel identifier={selection.identifier} />
        ) : selection.kind === 'zone' ? (
          <HuntZonePreviewPanel identifier={selection.identifier} />
        ) : selection.kind === 'npc' ? (
          <NpcPreviewPanel identifier={selection.identifier} />
        ) : (
          <CreaturePreviewPanel creatureId={selection.creatureId} kind={selection.kind} />
        )}
      </div>
    </aside>,
    document.body,
  );
}
