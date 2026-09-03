import React from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from './cn';

export const TableContainer = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => <div ref={ref} className={cn('ds-table-wrap', className)} {...props} />,
);
TableContainer.displayName = 'TableContainer';

export const Table = React.forwardRef<HTMLTableElement, React.TableHTMLAttributes<HTMLTableElement>>(
  ({ className, ...props }, ref) => <table ref={ref} className={cn('ds-table', className)} {...props} />,
);
Table.displayName = 'Table';

interface DataRegionProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Override the default viewport-relative max-height (e.g. "calc(100vh - 30rem)") */
  maxHeight?: string;
}

/**
 * DataRegion — viewport-aware scrollable data container.
 * Provides bounded max-height, internal vertical scrolling, theme-compatible
 * scrollbar, and sticky thead support when used with the Table/ds-table primitive.
 * Use instead of ad-hoc `overflow-y-auto max-h-*` on workspace data sections.
 */
export const DataRegion = React.forwardRef<HTMLDivElement, DataRegionProps>(
  ({ className, maxHeight, style, tabIndex = 0, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('ds-data-region', className)}
      style={maxHeight ? { ...style, maxHeight } : style}
      tabIndex={tabIndex}
      {...props}
    />
  ),
);
DataRegion.displayName = 'DataRegion';

interface PaginationControlsProps extends React.HTMLAttributes<HTMLElement> {
  skip: number;
  limit: number;
  total: number;
  loading?: boolean;
  onPrevious: () => void;
  onNext: () => void;
  previousLabel?: React.ReactNode;
  nextLabel?: React.ReactNode;
  statusLabel?: (values: { start: number; end: number; total: number; page: number; pageCount: number }) => React.ReactNode;
  navigationLabel?: string;
}

/** Offset-pagination navigation backed by an authoritative server total. */
export const PaginationControls: React.FC<PaginationControlsProps> = ({
  skip, limit, total, loading = false, onPrevious, onNext,
  previousLabel, nextLabel, statusLabel,
  navigationLabel, className, ...props
}) => {
  const { t } = useTranslation();
  const page = Math.floor(skip / limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const start = total === 0 ? 0 : skip + 1;
  const end = Math.min(skip + limit, total);
  return (
    <nav className={cn('ds-pagination', className)} aria-label={navigationLabel || t('pagination.label')} {...props}>
      <button type="button" className="app-button-secondary app-button-sm" disabled={loading || skip === 0} onClick={onPrevious}>
        {previousLabel || t('pagination.previous')}
      </button>
      <span role="status" aria-live="polite" className="ds-pagination-status">
        {statusLabel
          ? statusLabel({ start, end, total, page, pageCount })
          : t('pagination.status', { start, end, total, page, pageCount })}
      </span>
      <button type="button" className="app-button-secondary app-button-sm" disabled={loading || skip + limit >= total} onClick={onNext}>
        {nextLabel || t('pagination.next')}
      </button>
    </nav>
  );
};
