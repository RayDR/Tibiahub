import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCheck, faLanguage } from '@fortawesome/free-solid-svg-icons';

import { useViewportPopover } from '../hooks/useViewportPopover';

export default function LanguageSwitcher() {
    const { i18n, t } = useTranslation();
    const [isOpen, setIsOpen] = useState(false);
    const buttonRef = useRef<HTMLButtonElement | null>(null);
    const popoverStyle = useViewportPopover({
        open: isOpen,
        anchorRef: buttonRef,
        preferredWidth: 176,
    });

    const languages = [
        { code: 'en', name: t('language.english'), short: 'EN', region: t('language.regionUS') },
        { code: 'es', name: t('language.spanish'), short: 'ES', region: t('language.regionMX') },
    ];

    const activeCode = (i18n.resolvedLanguage || i18n.language || 'en').split('-')[0];
    const currentLang = languages.find(lang => lang.code === activeCode) || languages[0];

    useEffect(() => {
        if (!isOpen) return undefined;
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setIsOpen(false);
        };
        document.addEventListener('keydown', closeOnEscape);
        return () => document.removeEventListener('keydown', closeOnEscape);
    }, [isOpen]);

    const changeLanguage = (code: string) => {
        i18n.changeLanguage(code);
        setIsOpen(false);
    };

    const menu = isOpen ? createPortal(
        <>
            <div
                className="fixed inset-0 z-navbar"
                aria-hidden="true"
                onClick={() => setIsOpen(false)}
            />
            <div
                role="menu"
                style={popoverStyle}
                className="ds-dropdown z-dropdown overflow-x-hidden overflow-y-auto backdrop-blur-sm"
            >
                {languages.map((lang) => (
                    <button
                        key={lang.code}
                        role="menuitemradio"
                        aria-checked={activeCode === lang.code}
                        onClick={() => changeLanguage(lang.code)}
                        aria-label={t('a11y.switchLanguageTo', { language: lang.name })}
                        className={`flex w-full items-center gap-3 px-4 py-3 text-sm transition-all duration-300 ${
                            activeCode === lang.code
                                ? 'bg-primary/20 text-primary font-semibold'
                                : 'text-content-primary hover:bg-surface-inverse/5'
                        }`}
                    >
                        <span className="inline-flex w-8 items-center justify-center rounded border border-line px-1 py-0.5 text-[11px] font-semibold text-content-muted">
                            {lang.short}
                        </span>
                        <div className="min-w-0 flex-1 text-left">
                            <div className="truncate text-xs font-medium">{lang.name}</div>
                            <div className="truncate text-[10px] text-content-muted">{lang.region}</div>
                        </div>
                        {activeCode === lang.code ? <FontAwesomeIcon icon={faCheck} className="ml-auto text-xs" /> : null}
                    </button>
                ))}
            </div>
        </>,
        document.body,
    ) : null;

    return (
        <div className="relative">
            <button
                ref={buttonRef}
                onClick={() => setIsOpen(!isOpen)}
                aria-label={t('a11y.languageSelector')}
                aria-expanded={isOpen}
                aria-haspopup="menu"
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-content-muted transition-all duration-300 hover:bg-surface-inverse/5 hover:text-primary"
            >
                <FontAwesomeIcon icon={faLanguage} className="w-4" />
                <span className="text-xs font-semibold tracking-wide">{currentLang.short}</span>
            </button>
            {menu}
        </div>
    );
}
