import { useTranslation } from 'react-i18next';

import { useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck, faLanguage } from '@fortawesome/free-solid-svg-icons';

export default function LanguageSwitcher() {
    const { i18n, t } = useTranslation();
    const [isOpen, setIsOpen] = useState(false);

    const languages = [
        { code: 'en', name: t('language.english'), short: 'EN', region: t('language.regionUS') },
        { code: 'es', name: t('language.spanish'), short: 'ES', region: t('language.regionMX') },
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
                aria-label={t('a11y.languageSelector')}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-content-muted transition-all duration-300 hover:bg-surface-inverse/5 hover:text-primary"
            >
                <FontAwesomeIcon icon={faLanguage} className="w-4" />
                <span className="text-xs font-semibold tracking-wide">{currentLang.short}</span>
            </button>

            {isOpen && (
                <>
                    <div
                        className="fixed inset-0 z-base"
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="ds-dropdown absolute right-0 z-dropdown mt-2 w-44 overflow-hidden backdrop-blur-sm">
                        {languages.map((lang) => (
                            <button
                                key={lang.code}
                                onClick={() => changeLanguage(lang.code)}
                                aria-label={t('a11y.switchLanguageTo', { language: lang.name })}
                                className={`w-full flex items-center gap-3 px-4 py-3 text-sm transition-all duration-300 ${
                                    activeCode === lang.code
                                        ? 'bg-primary/20 text-primary font-semibold'
                                        : 'text-content-primary hover:bg-surface-inverse/5'
                                }`}
                            >
                                <span className="inline-flex w-8 items-center justify-center rounded border border-line px-1 py-0.5 text-[11px] font-semibold text-content-muted">
                                    {lang.short}
                                </span>
                                <div className="text-left">
                                    <div className="text-xs font-medium">{lang.name}</div>
                                    <div className="text-[10px] text-content-muted">{lang.region}</div>
                                </div>
                                {activeCode === lang.code ? <FontAwesomeIcon icon={faCheck} className="ml-auto text-xs" /> : null}
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
