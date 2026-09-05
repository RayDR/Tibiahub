import React from 'react';
import CyclopediaPersonalHistoryStrip from '../cyclopedia/CyclopediaPersonalHistoryStrip';
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

const CYCLOPEDIA_TAB_KEYS = new Set([
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
  const isCyclopediaTabs =
    items.length === CYCLOPEDIA_TAB_KEYS.size &&
    items.every((item) => CYCLOPEDIA_TAB_KEYS.has(item.key));
  const personalHistoryMode =
    isCyclopediaTabs && !compact &&
    (activeKey === 'items' || activeKey === 'zones')
      ? activeKey
      : null;

  return (
    <>
      {personalHistoryMode ? (
        <CyclopediaPersonalHistoryStrip mode={personalHistoryMode} />
      ) : null}
      <div
        className={cn(
          'app-tablist',
          compact && 'gap-1 p-1',
          className,
        )}
        role="tablist"
      >
        {items.map((item) => (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
            className={cn(
              'app-tab',
              compact && '!h-9 !px-2 !py-1',
              iconOnly &&
                '!w-9 !justify-center !px-1',
            )}
            title={item.label}
            aria-label={item.label}
            data-active={item.key === activeKey}
            role="tab"
            aria-selected={item.key === activeKey}
            type="button"
          >
            {item.icon}
            {!iconOnly ? (
              <span>{item.label}</span>
            ) : null}
          </button>
        ))}
      </div>
    </>
  );
};

export default AppTabs;
