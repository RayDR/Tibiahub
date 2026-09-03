import React from 'react';
import { cn } from './cn';

type Tone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'info';

const toneClasses: Record<Tone, string> = {
  neutral: 'border-line bg-surface-raised text-content-secondary',
  primary: 'border-primary/40 bg-primary-subtle text-primary',
  success: 'border-success/40 bg-success-subtle text-success',
  warning: 'border-warning/40 bg-warning-subtle text-warning',
  danger: 'border-danger/40 bg-danger-subtle text-danger',
  info: 'border-info/40 bg-info-subtle text-info',
};

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> { tone?: Tone }
export const Badge: React.FC<BadgeProps> = ({ tone = 'neutral', className, ...props }) => (
  <span className={cn('ds-badge', toneClasses[tone], className)} {...props} />
);

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> { tone?: Tone }
export const Alert: React.FC<AlertProps> = ({ tone = 'neutral', className, ...props }) => (
  <div role="alert" className={cn('ds-alert', toneClasses[tone], className)} {...props} />
);

interface StateProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  icon?: React.ReactNode;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<StateProps> = ({ icon, title, description, action, className, ...props }) => (
  <div className={cn('ds-empty-state', className)} {...props}>
    <div>
      {icon ? <div className="mb-3 text-3xl text-content-muted">{icon}</div> : null}
      {title ? <h3 className="text-lg font-semibold text-content-primary">{title}</h3> : null}
      {description ? <p className="mt-1 text-sm text-content-secondary">{description}</p> : null}
    </div>
    {action}
  </div>
);

export const LoadingState: React.FC<StateProps> = ({ icon, title, description, className, ...props }) => (
  <div className={cn('ds-loading-state', className)} role="status" aria-live="polite" {...props}>
    {icon ?? <span className="size-6 animate-spin rounded-full border-2 border-line border-t-primary" />}
    <div>
      {title ? <p className="font-medium text-content-primary">{title}</p> : null}
      {description ? <p className="mt-1 text-sm text-content-secondary">{description}</p> : null}
    </div>
  </div>
);

export const Skeleton: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({ className, ...props }) => (
  <div className={cn('ds-skeleton h-4 w-full', className)} aria-hidden="true" {...props} />
);

/**
 * ErrorState — distinct from EmptyState. Use for network/backend failures,
 * permission problems, and retryable error conditions.
 */
export const ErrorState: React.FC<StateProps> = ({ icon, title, description, action, className, ...props }) => (
  <div className={cn('ds-empty-state border border-danger/30 bg-danger-subtle', className)} role="alert" {...props}>
    <div>
      {icon ? <div className="mb-3 text-3xl text-danger">{icon}</div> : null}
      {title ? <h3 className="text-lg font-semibold text-danger">{title}</h3> : null}
      {description ? <p className="mt-1 text-sm text-content-secondary">{description}</p> : null}
    </div>
    {action}
  </div>
);

/**
 * DegradedState — for when an external dependency is unavailable but the
 * page can still show cached/partial data. Warning tone, informational.
 */
export const DegradedState: React.FC<StateProps> = ({ icon, title, description, action, className, ...props }) => (
  <div className={cn('ds-alert border-warning/40 bg-warning-subtle', className)} role="status" aria-live="polite" {...props}>
    {icon ? <div className="text-xl text-warning">{icon}</div> : null}
    <div className="min-w-0">
      {title ? <p className="font-semibold text-warning">{title}</p> : null}
      {description ? <p className="mt-1 text-sm text-content-secondary">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  </div>
);
