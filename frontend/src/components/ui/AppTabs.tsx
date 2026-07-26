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
}

const AppTabs: React.FC<AppTabsProps> = ({ items, activeKey, onChange, className }) => {
  return (
    <div className={cn('app-tablist', className)} role="tablist">
      {items.map((item) => (
        <button
          key={item.key}
          onClick={() => onChange(item.key)}
          className="app-tab"
          data-active={item.key === activeKey}
          role="tab"
          aria-selected={item.key === activeKey}
          type="button"
        >
          {item.icon}
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  );
};

export default AppTabs;
