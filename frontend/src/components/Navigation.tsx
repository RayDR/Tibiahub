import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BookOpen, Map, ScrollText, Shield, Settings } from 'lucide-react';
import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import LanguageSwitcher from './LanguageSwitcher';
import ThemeSwitcher from './ThemeSwitcher';

const Navigation: React.FC = () => {
  const location = useLocation();
  const { t } = useTranslation();
  const { isAuthenticated, user } = useAuth();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  const navItems = [
    { path: '/bestiary', label: t('nav.search'), icon: BookOpen },
    { path: '/recommendations', label: t('nav.planner'), icon: Map },
    { path: '/quests', label: t('nav.quests'), icon: ScrollText },
    ...(isAuthenticated ? [{ path: '/guild', label: t('nav.guild'), icon: Shield }] : []),
    ...(user?.is_superuser ? [{ path: '/admin', label: t('nav.admin'), icon: Settings }] : []),
  ];

  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      className="fixed top-0 left-0 right-0 z-50 px-2 sm:px-4 py-2 sm:py-4"
    >
      <div className="max-w-7xl mx-auto">
        <div className="bg-[rgba(15,23,42,0.85)] backdrop-blur-md border border-[rgba(148,163,184,0.1)] rounded-xl sm:rounded-2xl px-3 sm:px-6 py-2 sm:py-3 flex items-center justify-between shadow-2xl shadow-black/20">

          <Link to="/" className="flex items-center gap-2 sm:gap-3 group">
            <img 
              src="/assets/logo/tibiahub.png" 
              alt="Tibia Hub" 
              className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg shadow-lg group-hover:shadow-amber-500/20 transition-all duration-300 group-hover:scale-110"
            />
            <div className="hidden xs:flex flex-col leading-tight">
              <span className="font-serif font-bold text-sm tracking-tight text-white">
                <span className="text-amber-500">Tibia</span> Hub
              </span> 
            </div>
          </Link>

          <div className="flex items-center gap-0.5 sm:gap-1">
            {navItems.map((item) => {
              const active = isActive(item.path);
              const Icon = item.icon;

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`
                    relative px-4 py-2 rounded-xl flex items-center gap-2 transition-all duration-300
                    ${active
                      ? 'text-amber-400 bg-white/5 shadow-inner'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                    }
                  `}
                >
                  <Icon size={18} className={active ? "text-amber-400" : ""} />
                  <span className="hidden md:block font-medium text-sm">{item.label}</span>
                  {active && (
                    <motion.div
                      layoutId="nav-glow"
                      className="absolute inset-0 rounded-xl bg-gradient-to-r from-amber-500/10 to-orange-500/10"
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
