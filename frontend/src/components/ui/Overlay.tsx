import React from 'react';
import { cn } from './cn';

interface DialogProps extends React.HTMLAttributes<HTMLDivElement> {
  open: boolean;
  onClose: () => void;
  label: string;
}

export const Dialog: React.FC<DialogProps> = ({ open, onClose, label, className, children, ...props }) => {
  if (!open) return null;
  return (
    <div className="ds-dialog-backdrop" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={label}
        className={cn('ds-dialog', className)}
        onMouseDown={(event) => event.stopPropagation()}
        {...props}
      >
        {children}
      </div>
    </div>
  );
};

export const Tooltip: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div role="tooltip" className={cn('ds-tooltip', className)} {...props} />
);

export const Dropdown: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div role="menu" className={cn('ds-dropdown', className)} {...props} />
);
