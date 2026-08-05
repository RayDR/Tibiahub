import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { BookOpen, ChevronDown, Home, Map, Settings, Shield } from 'lucide-react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../context/AuthContext';
import { cyclopediaSections } from '../config/cyclopediaSections';
import LanguageSwitcher from './LanguageSwitcher';
import NotificationIndicator from './NotificationIndicator';
import ThemeSwitcher from './ThemeSwitcher';
import AccountMenu from './account/AccountMenu';
import { Container } from './ui';

interface NavigationItem {
  path: string;
  label: string;
  icon: typeof Home;
}

export default function Navigation() {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const [cyclopediaMenuOpen, setCyclopediaMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    if (path === '/cyclopedia') return location.pathname === '/cyclopedia' || /^\/(creatures|quests|npcs|locations)\//.test(location.pathname);
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const primaryItems: NavigationItem[] = [
    { path: '/', label: t('nav.home'), icon: Home },
    { path: '/cyclopedia', label: t('nav.search'), icon: BookOpen },
    { path: '/planner', label: t('nav.planner'), icon: Map },
    ...(isAuthenticated ? [{ path: '/guild', label: t('nav.guild'), icon: Shield }] : []),
    ...(user?.is_superuser ? [{ path: '/admin', label: t('nav.admin'), icon: Settings }] : []),
  ];

  useEffect(() => {
    if (!cyclopediaMenuOpen) return undefined;
    const closeOutside = (event: MouseEvent | TouchEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setCyclopediaMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setCyclopediaMenuOpen(false);
    };
    document.addEventListener('mousedown', closeOutside);
    document.addEventListener('touchstart', closeOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('mousedown', closeOutside);
      document.removeEventListener('touchstart', closeOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [cyclopediaMenuOpen]);

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-sticky">
        <Container className="pt-2 sm:pt-3">
          <div className="app-nav-shell flex items-center justify-between rounded-xl px-2 py-1.5 shadow-lg backdrop-blur-md sm:px-3">
            <Link to="/" className="flex min-h-11 min-w-0 items-center gap-2 rounded-lg px-1.5" aria-label={t('shell.homeLabel')}>
              <img src="/assets/logo/tibiahub.png" alt="" className="size-8 shrink-0 rounded-lg sm:size-9" />
              <span className="hidden font-serif text-sm font-bold text-content-primary sm:inline"><span className="text-primary">Tibia</span>Hub</span>
            </Link>

            <nav className="hidden min-w-0 items-center gap-1 md:flex" aria-label={t('shell.primaryNavigation')}>
              {primaryItems.map(item => {
                const Icon = item.icon;
                if (item.path === '/cyclopedia') {
                  return <div ref={menuRef} key={item.path} className="relative flex">
                    <Link to={item.path} className="app-nav-link flex min-h-11 items-center gap-2 rounded-l-lg px-3" data-active={isActive(item.path)}><Icon className="size-4" /><span>{item.label}</span></Link>
                    <button type="button" className="app-nav-link min-h-11 rounded-r-lg px-2" aria-label={t('a11y.openCyclopediaMenu')} aria-expanded={cyclopediaMenuOpen} onClick={() => setCyclopediaMenuOpen(value => !value)}><ChevronDown className={`size-4 transition-transform ${cyclopediaMenuOpen ? 'rotate-180' : ''}`} /></button>
                    {cyclopediaMenuOpen ? <div className="ds-dropdown absolute left-0 top-full mt-2 w-56">
                      {cyclopediaSections.map(entry => <button key={entry.key} type="button" onClick={() => { setCyclopediaMenuOpen(false); navigate(`/cyclopedia?tab=${entry.key}`); }} className="flex min-h-11 w-full items-center gap-2 rounded-sm px-3 text-left text-sm text-content-secondary hover:bg-surface-hover hover:text-content-primary"><FontAwesomeIcon icon={entry.icon} className="w-4" /><span>{t(entry.i18nLabel)}</span></button>)}
                    </div> : null}
                  </div>;
                }
                return <Link key={item.path} to={item.path} className="app-nav-link flex min-h-11 items-center gap-2 rounded-lg px-3" data-active={isActive(item.path)}><Icon className="size-4" /><span>{item.label}</span></Link>;
              })}
            </nav>

            <div className="flex shrink-0 items-center gap-0.5">
              <LanguageSwitcher />
              {isAuthenticated ? <NotificationIndicator /> : null}
              <ThemeSwitcher />
              {isAuthenticated ? <AccountMenu /> : <Link to="/login" className="app-button-primary app-button-sm ml-1">{t('auth.login')}</Link>}
            </div>
          </div>
        </Container>
      </header>

      <nav className="app-mobile-nav fixed inset-x-0 bottom-0 z-sticky border-t border-line bg-surface-overlay px-1 pt-1 backdrop-blur-md md:hidden" aria-label={t('shell.mobileNavigation')}>
        <div className="app-mobile-nav-grid mx-auto max-w-xl" style={{ '--mobile-nav-count': primaryItems.length } as React.CSSProperties}>
          {primaryItems.map(item => { const Icon = item.icon; return <Link key={item.path} to={item.path} className="app-mobile-nav-link" data-active={isActive(item.path)} aria-current={isActive(item.path) ? 'page' : undefined}><Icon className="size-5" /><span className="max-w-full truncate px-1">{item.label}</span></Link>; })}
        </div>
      </nav>
    </>
  );
}
