import React from 'react';
import { ChevronRight } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { IconDefinition } from '@fortawesome/fontawesome-svg-core';
import { TIBIAHUB_TITLE_ICONS, type TibiaHubTitleIconKey } from '../../assets/brand/brandTitleIcons';
import { cn } from './cn';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  icon?: IconDefinition;
  iconElement?: React.ReactNode;
  eyebrow?: string;
  breadcrumbs?: Array<{ label: string; to?: string }>;
  primaryAction?: React.ReactNode;
  secondaryActions?: React.ReactNode;
  align?: 'left' | 'center';
  size?: 'md' | 'lg';
  contained?: boolean;
  className?: string;
}

const routeTitleIcon = (pathname: string): TibiaHubTitleIconKey | null => {
  if (pathname === '/cyclopedia') return 'cyclopedia';
  if (pathname === '/planner') return 'huntPlanner';
  return null;
};

const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  icon,
  iconElement,
  eyebrow,
  breadcrumbs,
  primaryAction,
  secondaryActions,
  align = 'left',
  size = 'lg',
  contained = false,
  className,
}) => {
  const { pathname } = useLocation();
  const alignClass = align === 'left' ? 'text-left' : 'text-center';
  const titleSizeClass = size === 'md' ? 'app-page-title-md' : '';
  const brandIconKey = routeTitleIcon(pathname);
  const routeIcon = brandIconKey ? (
    <img
      src={TIBIAHUB_TITLE_ICONS[brandIconKey]}
      alt=""
      aria-hidden="true"
      draggable={false}
      className="app-page-brand-icon size-14 shrink-0 object-contain drop-shadow-lg sm:size-16"
    />
  ) : null;
  const resolvedIcon = iconElement || routeIcon;

  return (
    <header
      className={cn('app-page-header', contained && 'app-page-header-contained', alignClass, className)}
      data-brand-header={brandIconKey || undefined}
    >
      {breadcrumbs?.length ? (
        <nav aria-label={eyebrow || title} className="mb-3 flex min-w-0 flex-wrap items-center gap-1 text-xs text-content-muted">
          {breadcrumbs.map((item, index) => (
            <React.Fragment key={`${item.label}-${index}`}>
              {index > 0 ? <ChevronRight className="size-3.5 shrink-0" aria-hidden="true" /> : null}
              {item.to ? <Link to={item.to} className="truncate hover:text-content-primary">{item.label}</Link> : <span className="truncate text-content-secondary" aria-current="page">{item.label}</span>}
            </React.Fragment>
          ))}
        </nav>
      ) : null}
      <div className={cn('flex min-w-0 flex-col gap-4 sm:flex-row sm:items-end sm:justify-between', align === 'center' && 'sm:block')}>
        <div className="min-w-0">
          {eyebrow ? <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-primary">{eyebrow}</p> : null}
          <h1 className={cn('app-page-title', titleSizeClass, 'inline-flex items-center gap-3')}>
            {resolvedIcon ? <span className="inline-grid shrink-0 place-items-center text-primary">{resolvedIcon}</span> : icon ? <FontAwesomeIcon icon={icon} className="text-primary" /> : null}
            <span className="min-w-0">{title}</span>
          </h1>
          {subtitle ? <p className={cn('app-page-subtitle', align === 'left' && 'mx-0')}>{subtitle}</p> : null}
        </div>
        {(primaryAction || secondaryActions) ? (
          <div className={cn('flex min-w-0 max-w-full flex-wrap items-center gap-2 sm:flex-[0_1_auto]', align === 'center' && 'mt-4 justify-center')}>
            {secondaryActions}
            {primaryAction}
          </div>
        ) : null}
      </div>
    </header>
  );
};

export default PageHeader;
