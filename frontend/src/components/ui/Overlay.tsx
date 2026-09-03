import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { cn } from './cn';

interface DialogProps extends React.HTMLAttributes<HTMLDivElement> {
  open: boolean;
  onClose: () => void;
  label: string;
  /** Optional ID of a description element for aria-describedby */
  descriptionId?: string;
}

export const Dialog: React.FC<DialogProps> = ({ open, onClose, label, descriptionId, className, children, ...props }) => {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);
  useEffect(() => {
    if (!open) return undefined;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusable = () => Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') || []);
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current();
      if (event.key === 'Tab') {
        const items = focusable();
        if (!items.length) { event.preventDefault(); dialogRef.current?.focus(); return; }
        const first = items[0]; const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    requestAnimationFrame(() => { const items = focusable(); (items[0] || dialogRef.current)?.focus(); });
    return () => { document.removeEventListener('keydown', closeOnEscape); previousFocus?.focus(); };
  }, [open]);

  if (!open) return null;
  return createPortal(
    <div className="ds-dialog-backdrop" onMouseDown={onClose}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className={cn('ds-dialog', className)}
        onMouseDown={(event) => event.stopPropagation()}
        {...props}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
};

/** Structured dialog header — sticky, contains title and optional close button. */
export const DialogHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div className={cn('ds-dialog-header', className)} {...props} />
);

/** Structured dialog body — scrollable, takes remaining vertical space. */
export const DialogBody: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div className={cn('ds-dialog-body', className)} {...props} />
);

/** Structured dialog footer — sticky at bottom, contains action buttons. */
export const DialogFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div className={cn('ds-dialog-footer', className)} {...props} />
);

export const Tooltip: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div role="tooltip" className={cn('ds-tooltip', className)} {...props} />
);

export const Dropdown: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div role="menu" className={cn('ds-dropdown', className)} {...props} />
);
