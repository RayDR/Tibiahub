import React from 'react';
import { cn } from './cn';

type DivProps = React.HTMLAttributes<HTMLDivElement>;
type PageVariant = 'default' | 'focused';

interface PageProps extends DivProps {
  variant?: PageVariant;
}

export const Container = React.forwardRef<HTMLDivElement, DivProps>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('ds-container', className)} {...props} />
));
Container.displayName = 'Container';

export const Page = React.forwardRef<HTMLDivElement, PageProps>(({ className, variant = 'default', ...props }, ref) => (
  <div
    ref={ref}
    className={cn('ds-page', variant === 'focused' && 'ds-page-focused', className)}
    {...props}
  />
));
Page.displayName = 'Page';

export const Section = React.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement>>(
  ({ className, ...props }, ref) => <section ref={ref} className={cn('ds-section', className)} {...props} />,
);
Section.displayName = 'Section';

export const Panel = React.forwardRef<HTMLDivElement, DivProps>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('ds-panel', className)} {...props} />
));
Panel.displayName = 'Panel';

export const Card = React.forwardRef<HTMLDivElement, DivProps>(({ className, ...props }, ref) => (
  <article ref={ref} className={cn('ds-card', className)} {...props} />
));
Card.displayName = 'Card';

export const Toolbar = React.forwardRef<HTMLDivElement, DivProps>(({ className, ...props }, ref) => (
  <div ref={ref} role="toolbar" className={cn('ds-toolbar', className)} {...props} />
));
Toolbar.displayName = 'Toolbar';

interface SplitViewProps extends DivProps {
  sidebarPosition?: 'start' | 'end';
}

export const SplitView = React.forwardRef<HTMLDivElement, SplitViewProps>(
  ({ sidebarPosition = 'end', className, ...props }, ref) => (
    <div ref={ref} className={cn('ds-split-view', className)} data-sidebar={sidebarPosition} {...props} />
  ),
);
SplitView.displayName = 'SplitView';

export const Sidebar = React.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement>>(
  ({ className, ...props }, ref) => <aside ref={ref} className={cn('ds-sidebar', className)} {...props} />,
);
Sidebar.displayName = 'Sidebar';

export const ScrollablePanel = React.forwardRef<HTMLDivElement, DivProps>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('ds-scrollable-panel', className)} {...props} />
));
ScrollablePanel.displayName = 'ScrollablePanel';
