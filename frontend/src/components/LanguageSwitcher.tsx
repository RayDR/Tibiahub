import { useTranslation } from 'react-i18next';

import { useState } from 'react';

export default function LanguageSwitcher() {
    const { i18n } = useTranslation();
    const [isOpen, setIsOpen] = useState(false);

    const languages = [
        { code: 'en', name: 'English', flag: '🇺🇸', short: 'EN' },
        { code: 'es', name: 'Español', flag: '🇲🇽', short: 'ES' },
    ];

    const activeCode = (i18n.resolvedLanguage || i18n.language || 'en').split('-')[0];
    const currentLang = languages.find(lang => lang.code === activeCode) || languages[0];

    const changeLanguage = (code: string) => {
        i18n.changeLanguage(code);
        setIsOpen(false);
    };

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                aria-label={`Language: ${currentLang.name}`}
                className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:text-amber-500 transition-all duration-300 rounded-lg hover:bg-white/5 group"
            >
                <span className="text-2xl transition-transform duration-300 group-hover:scale-110">{currentLang.flag}</span>
                <span className="hidden md:inline text-xs font-semibold tracking-wide text-slate-400">{currentLang.short}</span>
            </button>

            {isOpen && (
                <>
                    <div 
                        className="fixed inset-0 z-10" 
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="absolute right-0 mt-2 w-40 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-20 overflow-hidden backdrop-blur-sm">
                        {languages.map((lang) => (
                            <button
                                key={lang.code}
                                onClick={() => changeLanguage(lang.code)}
                                aria-label={`Switch language to ${lang.name}`}
                                className={`w-full flex items-center justify-center gap-3 px-4 py-3 text-sm transition-all duration-300 ${
                                    activeCode === lang.code
                                        ? 'bg-amber-600/20 text-amber-500 font-semibold'
                                        : 'text-slate-300 hover:bg-slate-800 hover:scale-105'
                                }`}
                            >
                                <span className="text-2xl">{lang.flag}</span>
                                <span className="text-xs font-medium">{lang.short}</span>
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
