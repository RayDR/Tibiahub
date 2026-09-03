import { ReactNode } from 'react';
import { ChevronRight, Home } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import Navigation from '../Navigation';
import { Container } from '../ui';
import { SuggestImprovementLink } from '../feedback/GitHubFeedbackLink';

function currentContext(pathname: string, t: (key: string) => string): { parent?: { label: string; to: string }; label: string } | null {
  if (pathname === '/') return null;
  if (pathname.startsWith('/admin')) return { parent: pathname === '/admin' ? undefined : { label: t('nav.admin'), to: '/admin' }, label: pathname === '/admin' ? t('nav.admin') : t('shell.context.admin') };
  if (pathname.startsWith('/guild')) return { parent: pathname === '/guild' ? undefined : { label: t('nav.guild'), to: '/guild' }, label: pathname === '/guild' ? t('nav.guild') : t('shell.context.guild') };
  if (pathname === '/cyclopedia') return { label: t('nav.search') };
  if (pathname.startsWith('/creatures/')) return { parent: { label: t('nav.search'), to: '/cyclopedia?tab=creatures' }, label: t('shell.context.creature') };
  if (pathname.startsWith('/items/')) return { parent: { label: t('nav.search'), to: '/cyclopedia?tab=items' }, label: t('shell.context.item') };
  if (pathname.startsWith('/hunt-zones/')) return { parent: { label: t('nav.search'), to: '/cyclopedia?tab=zones' }, label: t('shell.context.huntZone') };
  if (pathname.startsWith('/quests/')) return { parent: { label: t('nav.search'), to: '/cyclopedia?tab=quests' }, label: t('shell.context.quest') };
  if (pathname === '/npcs') return { parent: { label: t('nav.search'), to: '/cyclopedia' }, label: t('nav.npcs') };
  if (pathname.startsWith('/npcs/')) return { parent: { label: t('nav.npcs'), to: '/npcs' }, label: t('shell.context.npc') };
  if (pathname.startsWith('/locations/')) return { parent: { label: t('nav.search'), to: '/cyclopedia?tab=zones' }, label: t('shell.context.location') };
  if (pathname === '/planner') return { label: t('nav.planner') };
  if (pathname === '/map') return { label: t('nav.map') };
  if (pathname === '/profile') return { label: t('shell.profile') };
  if (pathname.startsWith('/login') || pathname.startsWith('/register') || pathname.startsWith('/reset-password')) return { label: t('shell.context.account') };
  return null;
}

export default function AppShell({ children, dataVersion }: { children: ReactNode; dataVersion?: string }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const context = currentContext(pathname, t);
  const isMapWorkspace = pathname === '/map';

  return <div className="app-shell flex min-h-screen flex-col text-content-primary">
    <Navigation />
    <div className={`app-shell-main flex min-h-0 flex-1 flex-col ${isMapWorkspace ? 'app-shell-main-map' : ''}`}>
      {context && !isMapWorkspace ? <Container><nav className="app-context-bar gap-1 text-xs text-content-muted" aria-label={t('shell.breadcrumbs')}>
        <Link to="/" className="inline-flex min-h-9 items-center gap-1 rounded px-1 hover:text-content-primary"><Home className="size-3.5" /><span className="sr-only">{t('nav.home')}</span></Link>
        <ChevronRight className="size-3.5" aria-hidden="true" />
        {context.parent ? <><Link to={context.parent.to} className="rounded px-1 hover:text-content-primary">{context.parent.label}</Link><ChevronRight className="size-3.5" aria-hidden="true" /></> : null}
        <span className="truncate text-content-secondary" aria-current="page">{context.label}</span>
      </nav></Container> : null}
      <main className="min-h-0 flex-1">
        {isMapWorkspace ? children : <Container>{children}</Container>}
      </main>
      {!isMapWorkspace ? <footer className="mt-16 border-t border-line py-8 text-center">
        <p className="text-sm text-content-secondary">{t('footer.project', { version: dataVersion || t('footer.unavailable') })}</p>
        <p className="mt-2 text-xs text-content-muted">{t('footer.trademark')}</p>
        <p className="mt-2 text-xs text-content-muted">{t('footer.dataSource')} <a href="https://tibia.fandom.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary-hover">TibiaWiki</a></p>
        <SuggestImprovementLink className="mt-3 justify-center" />
      </footer> : null}
    </div>
  </div>;
}
