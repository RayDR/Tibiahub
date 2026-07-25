import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle, XCircle, AlertCircle, Info, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
    id: string;
    type: ToastType;
    message: string;
    duration?: number;
}

interface ToastContextType {
    showToast: (message: string, type: ToastType, duration?: number) => void;
    success: (message: string, duration?: number) => void;
    error: (message: string, duration?: number) => void;
    warning: (message: string, duration?: number) => void;
    info: (message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { t } = useTranslation();
    const [toasts, setToasts] = useState<Toast[]>([]);

    const removeToast = useCallback((id: string) => {
        setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, []);

    const showToast = useCallback((message: string, type: ToastType, duration: number = 5000) => {
        const id = `toast-${Date.now()}-${Math.random()}`;
        const newToast: Toast = { id, type, message, duration };

        setToasts((prev) => [...prev, newToast]);

        if (duration > 0) {
            setTimeout(() => removeToast(id), duration);
        }
    }, [removeToast]);

    const success = useCallback((message: string, duration?: number) => {
        showToast(message, 'success', duration);
    }, [showToast]);

    const error = useCallback((message: string, duration?: number) => {
        showToast(message, 'error', duration);
    }, [showToast]);

    const warning = useCallback((message: string, duration?: number) => {
        showToast(message, 'warning', duration);
    }, [showToast]);

    const info = useCallback((message: string, duration?: number) => {
        showToast(message, 'info', duration);
    }, [showToast]);

    const getToastStyles = (type: ToastType) => {
        const baseStyles = "flex items-start gap-3 p-4 rounded-lg border shadow-lg backdrop-blur-sm min-w-[320px] max-w-md";

        switch (type) {
            case 'success':
                return `${baseStyles} bg-surface-overlay border-success/60 text-content-primary`;
            case 'error':
                return `${baseStyles} bg-surface-overlay border-danger/60 text-content-primary`;
            case 'warning':
                return `${baseStyles} bg-surface-overlay border-warning/60 text-content-primary`;
            case 'info':
                return `${baseStyles} bg-surface-overlay border-info/60 text-content-primary`;
        }
    };

    const getIcon = (type: ToastType) => {
        const iconClass = "w-5 h-5 flex-shrink-0 mt-0.5";
        switch (type) {
            case 'success':
                return <CheckCircle className={`${iconClass} text-success`} />;
            case 'error':
                return <XCircle className={`${iconClass} text-danger`} />;
            case 'warning':
                return <AlertCircle className={`${iconClass} text-warning`} />;
            case 'info':
                return <Info className={`${iconClass} text-info`} />;
        }
    };

    return (
        <ToastContext.Provider value={{ showToast, success, error, warning, info }}>
            {children}

            {/* Toast Container */}
            <div className="fixed top-4 right-4 z-toast space-y-2 pointer-events-none">
                {toasts.map((toast) => (
                    <div
                        key={toast.id}
                        className="ds-toast pointer-events-auto"
                    >
                        <div className={getToastStyles(toast.type)}>
                            {getIcon(toast.type)}
                            <div className="flex-1">
                                <p className="text-sm font-medium leading-relaxed">{toast.message}</p>
                            </div>
                            <button
                                onClick={() => removeToast(toast.id)}
                                className="text-content-primary/70 hover:text-content-primary transition-colors flex-shrink-0"
                                aria-label={t('common.close')}
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
};
