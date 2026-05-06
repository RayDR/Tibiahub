import React from 'react';

interface AppButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost';
}

const AppButton: React.FC<AppButtonProps> = ({ variant = 'primary', className = '', ...props }) => {
  const variantClass = variant === 'primary' ? 'app-button-primary' : 'app-button-ghost';
  return <button className={`${variantClass} ${className}`.trim()} {...props} />;
};

export default AppButton;
