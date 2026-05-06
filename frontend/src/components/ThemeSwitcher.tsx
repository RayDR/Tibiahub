import { useState, useEffect } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck, faChessRook, faMountain, faPalette } from '@fortawesome/free-solid-svg-icons';
import { useTranslation } from 'react-i18next';

export default function ThemeSwitcher() {
    const { t } = useTranslation();
    const [theme, setTheme] = useState<'default' | 'medieval' | 'tibia-stone'>('default');
    const [isOpen, setIsOpen] = useState(false);

    useEffect(() => {
        const savedTheme = (localStorage.getItem('theme') as 'default' | 'medieval' | 'tibia-stone') || 'default';
        setTheme(savedTheme);
        document.documentElement.setAttribute('data-theme', savedTheme);
    }, []);

    const changeTheme = (newTheme: 'default' | 'medieval' | 'tibia-stone') => {
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
        document.documentElement.setAttribute('data-theme', newTheme);
        setIsOpen(false);
    };

    const themes = [
        { id: 'default', name: t('themes.default'), icon: faPalette, description: t('themes.defaultDescription') },
        { id: 'medieval', name: t('themes.medieval'), icon: faChessRook, description: t('themes.medievalDescription') },
        { id: 'tibia-stone', name: t('themes.tibiaStone'), icon: faMountain, description: t('themes.tibiaStoneDescription') },
    ];

    const currentTheme = themes.find((themeItem) => themeItem.id === theme) || themes[0];

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                aria-label={t('a11y.themeSelector')}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[color:var(--color-text-muted)] transition-all duration-300 hover:bg-white/5 hover:text-[color:var(--color-primary)] group"
            >
                <FontAwesomeIcon icon={faPalette} className="w-4 h-4 transition-transform duration-300 group-hover:rotate-12" />
                <span className="hidden md:inline text-xs font-medium">{currentTheme.name}</span>
            </button>

            {isOpen && (
                <>
                    <div 
                        className="fixed inset-0 z-10" 
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="absolute right-0 z-20 mt-2 w-64 overflow-hidden rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-surface)] shadow-xl backdrop-blur-sm">
                        {themes.map((themeItem) => (
                            <button
                                key={themeItem.id}
                                onClick={() => changeTheme(themeItem.id as 'default' | 'medieval' | 'tibia-stone')}
                                aria-label={t('a11y.switchThemeTo', { theme: themeItem.name })}
                                className={`w-full flex items-center gap-3 px-4 py-3 text-sm transition-all duration-300 ${
                                    theme === themeItem.id
                                        ? 'bg-[color:var(--color-primary)]/20 text-[color:var(--color-primary)] font-semibold'
                                        : 'text-[color:var(--color-text)] hover:bg-white/5'
                                }`}
                            >
                                <FontAwesomeIcon icon={themeItem.icon} className="text-lg" />
                                <div className="text-left flex-1">
                                    <div className="font-medium">{themeItem.name}</div>
                                    <div className="text-xs text-[color:var(--color-text-muted)]">{themeItem.description}</div>
                                </div>
                                {theme === themeItem.id && (
                                    <FontAwesomeIcon icon={faCheck} className="text-xs" />
                                )}
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
