import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle, XCircle, AlertCircle, Info, X } from 'lucide-react';

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
                return `${baseStyles} bg-emerald-900/90 border-emerald-600/50 text-emerald-100`;
            case 'error':
                return `${baseStyles} bg-red-900/90 border-red-600/50 text-red-100`;
            case 'warning':
                return `${baseStyles} bg-amber-900/90 border-amber-600/50 text-amber-100`;
            case 'info':
                return `${baseStyles} bg-blue-900/90 border-blue-600/50 text-blue-100`;
        }
    };

    const getIcon = (type: ToastType) => {
        const iconClass = "w-5 h-5 flex-shrink-0 mt-0.5";
        switch (type) {
            case 'success':
                return <CheckCircle className={`${iconClass} text-emerald-400`} />;
            case 'error':
                return <XCircle className={`${iconClass} text-red-400`} />;
            case 'warning':
                return <AlertCircle className={`${iconClass} text-amber-400`} />;
            case 'info':
                return <Info className={`${iconClass} text-blue-400`} />;
        }
    };

    return (
        <ToastContext.Provider value={{ showToast, success, error, warning, info }}>
            {children}
            
            {/* Toast Container */}
            <div className="fixed top-4 right-4 z-[9999] space-y-2 pointer-events-none">
                {toasts.map((toast) => (
                    <div
                        key={toast.id}
                        className="pointer-events-auto animate-in slide-in-from-right duration-300"
                    >
                        <div className={getToastStyles(toast.type)}>
                            {getIcon(toast.type)}
                            <div className="flex-1">
                                <p className="text-sm font-medium leading-relaxed">{toast.message}</p>
                            </div>
                            <button
                                onClick={() => removeToast(toast.id)}
                                className="text-white/70 hover:text-white transition-colors flex-shrink-0"
                                aria-label="Close notification"
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
