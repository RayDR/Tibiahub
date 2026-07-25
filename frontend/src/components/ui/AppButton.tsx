import React from 'react';
import { cn } from './cn';

interface AppButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

const AppButton: React.FC<AppButtonProps> = ({
  variant = 'primary', size = 'lg', loading = false, disabled, className, children, ...props
}) => {
  return (
    <button
      className={cn(`app-button-${variant}`, size !== 'lg' && `app-button-${size}`, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" /> : null}
      {children}
    </button>
  );
};

export default AppButton;
