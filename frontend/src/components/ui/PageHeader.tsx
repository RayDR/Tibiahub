import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { IconDefinition } from '@fortawesome/fontawesome-svg-core';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  icon?: IconDefinition;
  align?: 'left' | 'center';
  size?: 'md' | 'lg';
}

const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  icon,
  align = 'center',
  size = 'lg',
}) => {
  const alignClass = align === 'left' ? 'text-left' : 'text-center';
  const titleSizeClass = size === 'md' ? 'app-page-title-md' : '';

  return (
    <div className={`app-page-header ${alignClass}`}>
      <h1 className={`app-page-title ${titleSizeClass} inline-flex items-center gap-3`}>
        {icon ? <FontAwesomeIcon icon={icon} className="text-primary" /> : null}
        <span>{title}</span>
      </h1>
      {subtitle ? <p className="app-page-subtitle">{subtitle}</p> : null}
    </div>
  );
};

export default PageHeader;
