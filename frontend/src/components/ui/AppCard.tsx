import React from 'react';

interface AppCardProps extends React.HTMLAttributes<HTMLDivElement> {
  alt?: boolean;
}

const AppCard: React.FC<AppCardProps> = ({ alt = false, className = '', children, ...props }) => {
  const base = alt ? 'app-surface-alt' : 'app-surface';
  return (
    <div className={`${base} ${className}`.trim()} {...props}>
      {children}
    </div>
  );
};

export default AppCard;
