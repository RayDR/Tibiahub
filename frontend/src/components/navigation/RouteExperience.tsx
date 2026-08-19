import { useEffect, useRef, useState } from 'react';
import { ArrowUp } from 'lucide-react';
import { useLocation, useNavigationType } from 'react-router-dom';

const SCROLL_PREFIX = 'tibiahub:route-scroll:';
const RESTORE_FRAME_LIMIT = 90;

function scrollKey(locationKey: string): string {
  return `${SCROLL_PREFIX}${locationKey}`;
}

function loadScroll(locationKey: string): number | null {
  try {
    const raw = sessionStorage.getItem(scrollKey(locationKey));
    if (!raw) return null;
    const value = Number(raw);
    return Number.isFinite(value) && value >= 0 ? value : null;
  } catch {
    return null;
  }
}

function saveScroll(locationKey: string): void {
  try {
    sessionStorage.setItem(scrollKey(locationKey), String(Math.max(0, window.scrollY)));
  } catch {
    // Navigation must never fail because storage is unavailable.
  }
}

function maximumScrollY(): number {
  const documentHeight = Math.max(
    document.documentElement.scrollHeight,
    document.body?.scrollHeight || 0,
  );
  return Math.max(0, documentHeight - window.innerHeight);
}

/**
 * Keeps browser-history scroll checkpoints across client-side detail navigation.
 *
 * React Router already gives every history entry a stable location key. We save
 * the current Y position under that key before an entry unmounts and restore it
 * only for POP navigation. On infinite-scroll screens, restoration advances to
 * the currently reachable bottom while waiting so the existing sentinel can
 * repopulate missing pages until the original checkpoint exists again.
 */
export default function RouteExperience() {
  const location = useLocation();
  const navigationType = useNavigationType();
  const previousPathnameRef = useRef(location.pathname);
  const [showBackToTop, setShowBackToTop] = useState(false);

  useEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
  }, []);

  useEffect(() => {
    const locationKey = location.key;
    const previousPathname = previousPathnameRef.current;
    const pathnameChanged = previousPathname !== location.pathname;
    previousPathnameRef.current = location.pathname;

    let frame = 0;
    let attempts = 0;
    let cancelled = false;

    const target = navigationType === 'POP' ? loadScroll(locationKey) : null;

    const restore = () => {
      if (cancelled) return;

      if (navigationType === 'POP' && target != null && pathnameChanged) {
        const maxY = maximumScrollY();
        if (maxY >= target || attempts >= RESTORE_FRAME_LIMIT) {
          window.scrollTo({ top: Math.min(target, maxY), behavior: 'auto' });
          return;
        }

        // Make an infinite-scroll sentinel reachable while async/cached content
        // is rebuilding. This is intentionally immediate and only happens on
        // browser Back/Forward restoration.
        if (window.scrollY < maxY) {
          window.scrollTo({ top: maxY, behavior: 'auto' });
        }

        attempts += 1;
        frame = window.requestAnimationFrame(restore);
        return;
      }

      if (pathnameChanged && navigationType !== 'POP') {
        window.scrollTo({ top: 0, behavior: 'auto' });
      }
    };

    frame = window.requestAnimationFrame(restore);

    const persist = () => saveScroll(locationKey);
    window.addEventListener('pagehide', persist);

    return () => {
      cancelled = true;
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener('pagehide', persist);
      persist();
    };
  }, [location.key, location.pathname, navigationType]);

  useEffect(() => {
    const enabled =
      location.pathname === '/cyclopedia' ||
      location.pathname === '/planner';

    if (!enabled) {
      setShowBackToTop(false);
      return undefined;
    }

    let frame = 0;
    const update = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        setShowBackToTop(window.scrollY > 700);
      });
    };

    update();
    window.addEventListener('scroll', update, { passive: true });
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', update);
    };
  }, [location.pathname]);

  if (!showBackToTop) return null;

  return (
    <button
      type="button"
      aria-label="Back to top"
      title="Back to top"
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      className="fixed bottom-5 right-5 z-50 grid size-11 place-items-center rounded-full border border-line bg-surface-overlay/95 text-primary shadow-xl backdrop-blur transition hover:-translate-y-0.5 hover:border-primary/60 hover:bg-surface-active focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <ArrowUp className="size-5" aria-hidden="true" />
    </button>
  );
}
