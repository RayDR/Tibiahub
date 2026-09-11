import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useState,
  type CSSProperties,
  type RefObject,
} from 'react';

interface ViewportPopoverOptions {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
  preferredWidth: number;
  gap?: number;
  gutter?: number;
}

const hiddenStyle: CSSProperties = {
  position: 'fixed',
  visibility: 'hidden',
};

export function useViewportPopover({
  open,
  anchorRef,
  preferredWidth,
  gap = 8,
  gutter = 10,
}: ViewportPopoverOptions): CSSProperties {
  const [style, setStyle] = useState<CSSProperties>(hiddenStyle);

  const measure = useCallback(() => {
    const anchor = anchorRef.current;
    if (!open || !anchor) return;

    const viewport = window.visualViewport;
    const viewportLeft = viewport?.offsetLeft ?? 0;
    const viewportTop = viewport?.offsetTop ?? 0;
    const viewportWidth = viewport?.width ?? document.documentElement.clientWidth;
    const viewportHeight = viewport?.height ?? window.innerHeight;
    const usableWidth = Math.max(0, viewportWidth - gutter * 2);
    const width = Math.min(preferredWidth, usableWidth);
    const rect = anchor.getBoundingClientRect();

    // Menus are anchored to the trigger's right edge by default, then clamped
    // into the visible viewport so narrow devices never lose menu content.
    const preferredLeft = rect.right - width;
    const minimumLeft = viewportLeft + gutter;
    const maximumLeft = Math.max(
      minimumLeft,
      viewportLeft + viewportWidth - width - gutter,
    );
    const left = Math.min(Math.max(preferredLeft, minimumLeft), maximumLeft);
    const top = Math.max(viewportTop + gutter, rect.bottom + gap);
    const maxHeight = Math.max(
      120,
      viewportTop + viewportHeight - top - gutter,
    );

    setStyle({
      position: 'fixed',
      left,
      top,
      width,
      maxWidth: `calc(100vw - ${gutter * 2}px)`,
      maxHeight,
      visibility: 'visible',
    });
  }, [anchorRef, gap, gutter, open, preferredWidth]);

  useLayoutEffect(() => {
    if (!open) {
      setStyle(hiddenStyle);
      return;
    }
    measure();
  }, [measure, open]);

  useEffect(() => {
    if (!open) return undefined;

    let frame = 0;
    const schedule = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        measure();
      });
    };

    window.addEventListener('resize', schedule);
    window.addEventListener('scroll', schedule, true);
    window.visualViewport?.addEventListener('resize', schedule);
    window.visualViewport?.addEventListener('scroll', schedule);

    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', schedule);
      window.removeEventListener('scroll', schedule, true);
      window.visualViewport?.removeEventListener('resize', schedule);
      window.visualViewport?.removeEventListener('scroll', schedule);
    };
  }, [measure, open]);

  return style;
}
