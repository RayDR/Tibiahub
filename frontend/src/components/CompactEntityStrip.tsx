import type {
  PointerEvent as ReactPointerEvent,
} from 'react';
import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';

import ImageWithFallback from './ImageWithFallback';

export interface CompactEntityStripItem {
  id: string;
  name: string;
  to: string;
  imageUrl?: string;
}

interface CompactEntityStripProps {
  title: string;
  items: CompactEntityStripItem[];
  variant: 'rail' | 'chips';
  nudgeSessionKey?: string;
}

interface DragState {
  active: boolean;
  pointerId: number;
  startX: number;
  scrollLeft: number;
  moved: boolean;
}

export default function CompactEntityStrip({
  title,
  items,
  variant,
  nudgeSessionKey,
}: CompactEntityStripProps) {
  const containerRef =
    useRef<HTMLDivElement | null>(null);

  const dragRef = useRef<DragState>({
    active: false,
    pointerId: -1,
    startX: 0,
    scrollLeft: 0,
    moved: false,
  });

  useEffect(() => {
    if (
      variant !== 'rail' ||
      !nudgeSessionKey ||
      items.length < 2
    ) {
      return undefined;
    }

    const container = containerRef.current;

    if (!container) {
      return undefined;
    }

    const timers: number[] = [];
    const storageKey =
      `tibiahub:strip-nudge:${nudgeSessionKey}`;

    const startTimer = window.setTimeout(() => {
      if (
        container.scrollWidth <=
        container.clientWidth + 8
      ) {
        return;
      }

      try {
        if (
          window.sessionStorage.getItem(
            storageKey,
          ) === '1'
        ) {
          return;
        }

        window.sessionStorage.setItem(
          storageKey,
          '1',
        );
      } catch {
        // Storage may be unavailable in restricted mode.
      }

      if (
        window.matchMedia(
          '(prefers-reduced-motion: reduce)',
        ).matches
      ) {
        return;
      }

      const distance = Math.min(
        120,
        Math.max(
          64,
          container.clientWidth * 0.2,
        ),
      );

      const move = (
        delay: number,
        left: number,
      ) => {
        timers.push(
          window.setTimeout(() => {
            container.scrollTo({
              left,
              behavior: 'smooth',
            });
          }, delay),
        );
      };

      move(0, distance);
      move(650, 0);
      move(1250, distance * 0.75);
      move(1900, 0);
    }, 650);

    timers.push(startTimer);

    return () => {
      timers.forEach((timer) =>
        window.clearTimeout(timer),
      );
    };
  }, [
    items.length,
    nudgeSessionKey,
    variant,
  ]);

  if (items.length === 0) {
    return null;
  }

  const startDrag = (
    event: ReactPointerEvent<HTMLDivElement>,
  ) => {
    if (
      event.pointerType !== 'mouse' ||
      event.button !== 0
    ) {
      return;
    }

    const target = event.currentTarget;

    dragRef.current = {
      active: true,
      pointerId: event.pointerId,
      startX: event.clientX,
      scrollLeft: target.scrollLeft,
      moved: false,
    };

    target.setPointerCapture(event.pointerId);
  };

  const moveDrag = (
    event: ReactPointerEvent<HTMLDivElement>,
  ) => {
    const drag = dragRef.current;

    if (
      !drag.active ||
      drag.pointerId !== event.pointerId
    ) {
      return;
    }

    const delta = event.clientX - drag.startX;

    if (Math.abs(delta) > 4) {
      drag.moved = true;
    }

    event.currentTarget.scrollLeft =
      drag.scrollLeft - delta;
  };

  const finishDrag = (
    event: ReactPointerEvent<HTMLDivElement>,
  ) => {
    const drag = dragRef.current;

    if (
      !drag.active ||
      drag.pointerId !== event.pointerId
    ) {
      return;
    }

    drag.active = false;

    if (
      event.currentTarget.hasPointerCapture(
        event.pointerId,
      )
    ) {
      event.currentTarget.releasePointerCapture(
        event.pointerId,
      );
    }
  };

  return (
    <section
      aria-label={title}
      className={
        variant === 'rail'
          ? 'w-full'
          : 'min-w-0'
      }
    >
      <div
        className={
          variant === 'rail'
            ? 'mb-1.5 text-xs font-semibold uppercase tracking-wide text-primary'
            : 'sr-only'
        }
      >
        {title}
      </div>

      <div
        ref={containerRef}
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
        onClickCapture={(event) => {
          if (dragRef.current.moved) {
            event.preventDefault();
            event.stopPropagation();
            dragRef.current.moved = false;
          }
        }}
        className={[
          'flex min-w-0 select-none items-center overflow-x-auto',
          'overscroll-x-contain [scrollbar-width:none]',
          '[&::-webkit-scrollbar]:hidden',
          'touch-pan-x snap-x snap-proximity',
          variant === 'rail'
            ? 'cursor-grab gap-2 active:cursor-grabbing'
            : 'gap-1.5',
        ].join(' ')}
      >
        {variant === 'chips' ? (
          <span className="shrink-0 px-1 text-[10px] font-semibold uppercase tracking-wide text-primary">
            {title}
          </span>
        ) : null}

        {items.map((item) => (
          <Link
            key={item.id}
            to={item.to}
            draggable={false}
            onDragStart={(event) =>
              event.preventDefault()
            }
            title={item.name}
            className={
              variant === 'rail'
                ? [
                    'flex h-14 w-[9.25rem] shrink-0 snap-start',
                    'items-center gap-2 rounded-xl border border-line',
                    'bg-surface-raised px-2 transition',
                    'hover:border-primary/50 hover:bg-surface-active',
                  ].join(' ')
                : [
                    'inline-flex h-9 max-w-[10rem] shrink-0',
                    'items-center gap-1.5 rounded-full border border-line',
                    'bg-surface-raised px-2 transition',
                    'hover:border-primary/50 hover:bg-surface-active',
                  ].join(' ')
            }
          >
            <ImageWithFallback
              src={item.imageUrl || null}
              alt={item.name}
              className={
                variant === 'rail'
                  ? 'size-10 object-contain [image-rendering:pixelated]'
                  : 'size-6 object-contain [image-rendering:pixelated]'
              }
              containerClassName={
                variant === 'rail'
                  ? 'size-10 shrink-0'
                  : 'size-6 shrink-0'
              }
              fallbackLabel={item.name}
            />

            <span
              className={
                variant === 'rail'
                  ? 'line-clamp-2 text-xs font-semibold leading-tight text-content-primary'
                  : 'truncate text-xs font-semibold text-content-primary'
              }
            >
              {item.name}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
