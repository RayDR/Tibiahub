import { useState, useEffect } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck, faChessRook, faPalette } from '@fortawesome/free-solid-svg-icons';

export default function ThemeSwitcher() {
    const [theme, setTheme] = useState<'default' | 'medieval'>('default');
    const [isOpen, setIsOpen] = useState(false);

    useEffect(() => {
        const savedTheme = localStorage.getItem('theme') as 'default' | 'medieval' || 'default';
        setTheme(savedTheme);
        document.documentElement.setAttribute('data-theme', savedTheme);
    }, []);

    const changeTheme = (newTheme: 'default' | 'medieval') => {
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
        document.documentElement.setAttribute('data-theme', newTheme);
        setIsOpen(false);
    };

    const themes = [
        { id: 'default', name: 'Default', icon: faPalette, description: 'Modern dark theme' },
        { id: 'medieval', name: 'Medieval', icon: faChessRook, description: 'Gothic medieval theme' },
    ];

    const currentTheme = themes.find(t => t.id === theme) || themes[0];

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                aria-label="Change theme"
                className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:text-amber-500 transition-all duration-300 rounded-lg hover:bg-white/5 group"
            >
                <FontAwesomeIcon icon={faPalette} className="w-4 h-4 transition-transform duration-300 group-hover:rotate-12" />
                <FontAwesomeIcon icon={currentTheme.icon} className="text-base" />
            </button>

            {isOpen && (
                <>
                    <div 
                        className="fixed inset-0 z-10" 
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="absolute right-0 mt-2 w-56 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-20 overflow-hidden backdrop-blur-sm">
                        {themes.map((t) => (
                            <button
                                key={t.id}
                                onClick={() => changeTheme(t.id as 'default' | 'medieval')}
                                aria-label={`Use ${t.name} theme`}
                                className={`w-full flex items-center gap-3 px-4 py-3 text-sm transition-all duration-300 ${
                                    theme === t.id
                                        ? 'bg-amber-600/20 text-amber-500 font-semibold'
                                        : 'text-slate-300 hover:bg-slate-800 hover:scale-105'
                                }`}
                            >
                                <FontAwesomeIcon icon={t.icon} className="text-lg" />
                                <div className="text-left flex-1">
                                    <div className="font-medium">{t.name}</div>
                                    <div className="text-xs text-slate-400">{t.description}</div>
                                </div>
                                {theme === t.id && (
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
