import React from 'react';
import { cn } from './cn';
import { Card } from './Layout';

interface AppCardProps extends React.HTMLAttributes<HTMLDivElement> {
  alt?: boolean;
}

const AppCard: React.FC<AppCardProps> = ({ alt = false, className, children, ...props }) => {
  const base = alt ? 'app-surface-alt' : 'app-surface';
  return (
    <Card className={cn(base, className)} {...props}>
      {children}
    </Card>
  );
};

export default AppCard;
