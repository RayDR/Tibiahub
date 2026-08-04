import React from 'react';
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

const AppTabs: React.FC<AppTabsProps> = ({
  items,
  activeKey,
  onChange,
  className,
  compact = false,
  iconOnly = false,
}) => {
  return (
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
  );
};

export default AppTabs;
