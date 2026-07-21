import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { BookOpen, ChevronDown, Map, Shield, Settings } from 'lucide-react';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { useAuth } from '../context/AuthContext';
import LanguageSwitcher from './LanguageSwitcher';
import ThemeSwitcher from './ThemeSwitcher';
import { cyclopediaSections } from '../config/cyclopediaSections';

const Navigation: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();
  const [cyclopediaMenuOpen, setCyclopediaMenuOpen] = useState(false);
  const closeTimerRef = useRef<number | null>(null);
  const cyclopediaWrapperRef = useRef<HTMLDivElement | null>(null);

  const clearCloseTimer = () => {
    if (closeTimerRef.current !== null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const openCyclopediaMenu = () => {
    clearCloseTimer();
    setCyclopediaMenuOpen(true);
  };

  const scheduleCloseCyclopediaMenu = () => {
    clearCloseTimer();
    closeTimerRef.current = window.setTimeout(() => {
      setCyclopediaMenuOpen(false);
      closeTimerRef.current = null;
    }, 300);
  };

  useEffect(() => {
    return () => {
      clearCloseTimer();
    };
  }, []);

  useEffect(() => {
    if (!cyclopediaMenuOpen) return;
    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node;
      if (cyclopediaWrapperRef.current && !cyclopediaWrapperRef.current.contains(target)) {
        setCyclopediaMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setCyclopediaMenuOpen(false);
      }
    };
    window.addEventListener('mousedown', onPointerDown);
    window.addEventListener('touchstart', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('touchstart', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [cyclopediaMenuOpen]);

  const isActive = (path: string) => {
    if (path === '/cyclopedia') {
      return location.pathname === '/cyclopedia' || location.pathname.startsWith('/creatures/') || location.pathname.startsWith('/quests/');
    }
    return location.pathname === path;
  };

  const navItems = [
    { path: '/cyclopedia', label: t('nav.search'), icon: BookOpen },
    { path: '/planner', label: t('nav.planner'), icon: Map },
    ...(isAuthenticated
        ? [{ path: user?.is_superuser ? '/admin/guild-view' : '/guild', label: t('nav.guild'), icon: Shield }]
        : []),
    ...(user?.is_superuser ? [{ path: '/admin', label: t('nav.admin'), icon: Settings }] : []),
  ];

  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      className="fixed top-0 left-0 right-0 z-50 px-2 sm:px-4 py-2 sm:py-4"
    >
      <div className="max-w-7xl mx-auto">
        <div className="app-nav-shell backdrop-blur-md rounded-xl sm:rounded-2xl px-3 sm:px-6 py-2 sm:py-3 flex items-center justify-between shadow-2xl shadow-black/20">

          <Link to="/" className="flex items-center gap-2 sm:gap-3 group">
            <img 
              src="/assets/logo/tibiahub.png" 
              alt="Tibia Hub" 
              className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg shadow-lg group-hover:shadow-amber-500/20 transition-all duration-300 group-hover:scale-110"
            />
            <div className="hidden xs:flex flex-col leading-tight">
              <span className="font-serif font-bold text-sm tracking-tight text-[color:var(--color-text)]">
                <span className="text-[color:var(--color-primary)]">Tibia</span> Hub
              </span> 
            </div>
          </Link>

          <div className="flex items-center gap-0.5 sm:gap-1 min-w-0">
            <div
              ref={cyclopediaWrapperRef}
              className="relative"
              onMouseEnter={openCyclopediaMenu}
              onMouseLeave={scheduleCloseCyclopediaMenu}
              onFocusCapture={openCyclopediaMenu}
              onBlurCapture={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                  scheduleCloseCyclopediaMenu();
                }
              }}
            >
              <div className="flex items-center">
                <Link
                  to="/cyclopedia"
                  className={`app-nav-link relative px-4 py-2 rounded-l-xl flex items-center gap-2 transition-all duration-300 ${isActive('/cyclopedia') ? 'app-nav-link' : ''}`}
                  data-active={isActive('/cyclopedia')}
                >
                  <BookOpen size={18} />
                  <span className="hidden md:block font-medium text-sm">{t('nav.search')}</span>
                </Link>
                <button
                  type="button"
                  aria-label={t('a11y.openCyclopediaMenu')}
                  onClick={() => setCyclopediaMenuOpen((current) => !current)}
                  className="app-nav-link rounded-r-xl px-2 py-2"
                >
                  <ChevronDown size={16} className={`transition-transform ${cyclopediaMenuOpen ? 'rotate-180' : ''}`} />
                </button>
              </div>

              {cyclopediaMenuOpen && (
                <div className="absolute left-0 top-full mt-2 w-56 rounded-xl border border-[color:var(--color-border)] bg-[color:var(--color-surface)] p-1.5 shadow-2xl">
                  {cyclopediaSections.map((entry) => (
                    <button
                      key={entry.key}
                      type="button"
                      onClick={() => {
                        clearCloseTimer();
                        setCyclopediaMenuOpen(false);
                        navigate(`/cyclopedia?tab=${entry.key}`);
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-[color:var(--color-text-muted)] hover:bg-white/5 hover:text-[color:var(--color-text)]"
                    >
                      <FontAwesomeIcon icon={entry.icon} className="w-4" />
                      <span>{t(entry.i18nLabel)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {navItems.filter((item) => item.path !== '/cyclopedia').map((item) => {
              const active = isActive(item.path);
              const Icon = item.icon;

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className="app-nav-link relative px-4 py-2 rounded-xl flex items-center gap-2 transition-all duration-300"
                  data-active={active}
                >
                  <Icon size={18} />
                  <span className="hidden md:block font-medium text-sm">{item.label}</span>
                  {active && (
                    <motion.div
                      layoutId="nav-glow"
                      className="absolute inset-0 rounded-xl bg-gradient-to-r from-[color:var(--color-primary)]/15 to-[color:var(--color-primary-alt)]/15"
                      initial={false}
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    />
                  )}
                </Link>
              );
            })}

            {/* Language Selector Divider */}
            <div className="hidden sm:block w-px h-6 bg-slate-700 mx-1 sm:mx-2" />

            <LanguageSwitcher />
            
            <div className="hidden sm:block w-px h-6 bg-slate-700 mx-1" />
            
            <ThemeSwitcher />

          </div>
        </div>
      </div>
    </motion.nav>
  );
};

export default Navigation;
