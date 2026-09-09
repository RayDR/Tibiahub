import React, { useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import CyclopediaPersonalHistoryStrip, {
  type CyclopediaPersonalHistoryMode,
} from '../cyclopedia/CyclopediaPersonalHistoryStrip';
import CyclopediaPopularStrip, {
  type CyclopediaPopularMode,
} from '../cyclopedia/CyclopediaPopularStrip';
import { cn } from './cn';

export interface AppTabItem {
  key: string;
  label: string;
  icon?: React.ReactNode;
}

interface AppTabsProps {
  items: AppTabItem[];
  activeKey: string;
  onChange: (key: string) => void;
  className?: string;
  compact?: boolean;
  iconOnly?: boolean;
}

type CyclopediaMode = CyclopediaPersonalHistoryMode & CyclopediaPopularMode;

const CYCLOPEDIA_TAB_KEYS = new Set<CyclopediaMode>([
  'creatures',
  'bosses',
  'items',
  'quests',
  'zones',
  'npcs',
]);

const AppTabs: React.FC<AppTabsProps> = ({
  items,
  activeKey,
  onChange,
  className,
  compact = false,
  iconOnly = false,
}) => {
  const tabListRef = useRef<HTMLDivElement | null>(null);
  const [popularHost, setPopularHost] = useState<HTMLElement | null>(null);

  const isCyclopediaTabs =
    items.length === CYCLOPEDIA_TAB_KEYS.size &&
    items.every((item) => CYCLOPEDIA_TAB_KEYS.has(item.key as CyclopediaMode));
  const hasCanonicalCyclopediaChrome =
    isCyclopediaTabs &&
    !compact &&
    CYCLOPEDIA_TAB_KEYS.has(activeKey as CyclopediaMode);
  const cyclopediaMode = hasCanonicalCyclopediaChrome
    ? activeKey as CyclopediaMode
    : null;

  useLayoutEffect(() => {
    if (!hasCanonicalCyclopediaChrome) {
      setPopularHost(null);
      return undefined;
    }

    const tabList = tabListRef.current;
    const controlsCard = tabList?.closest<HTMLElement>('article.ds-card');
    const controlsWrapper = controlsCard?.parentElement;
    if (!controlsCard || !controlsWrapper) return undefined;

    const host = document.createElement('div');
    host.className = 'cyclopedia-popular-portal';
    host.dataset.cyclopediaContextPortal = 'popular';
    controlsWrapper.insertBefore(host, controlsCard.nextSibling);
    setPopularHost(host);

    return () => {
      setPopularHost((current) => current === host ? null : current);
      host.remove();
    };
  }, [hasCanonicalCyclopediaChrome]);

  return (
    <>
      {cyclopediaMode ? (
        <CyclopediaPersonalHistoryStrip mode={cyclopediaMode} />
      ) : null}

      <div
        ref={tabListRef}
        className={cn(
          'app-tablist',
          compact && 'gap-1 p-1',
          className,
        )}
        data-variant={isCyclopediaTabs ? 'cyclopedia' : undefined}
        data-compact={compact ? 'true' : 'false'}
        role="tablist"
      >
        {items.map((item) => (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
            className={cn(
              'app-tab',
              compact && '!h-9 !px-2 !py-1',
              iconOnly && '!w-9 !justify-center !px-1',
            )}
            title={item.label}
            aria-label={item.label}
            data-active={item.key === activeKey}
            data-tab-key={item.key}
            role="tab"
            aria-selected={item.key === activeKey}
            type="button"
          >
            {item.icon}
            {!iconOnly ? <span>{item.label}</span> : null}
          </button>
        ))}
      </div>

      {popularHost && cyclopediaMode
        ? createPortal(
            <CyclopediaPopularStrip mode={cyclopediaMode} />,
            popularHost,
          )
        : null}
    </>
  );
};

export default AppTabs;
