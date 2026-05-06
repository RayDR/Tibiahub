import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSearch } from '@fortawesome/free-solid-svg-icons';

interface AppInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  search?: boolean;
  onSearch?: () => void;
  searchAriaLabel?: string;
}

const AppInput: React.FC<AppInputProps> = ({ search = false, onSearch, searchAriaLabel = 'Search', className = '', ...props }) => {
  if (!search) {
    return <input className={`app-input ${className}`.trim()} {...props} />;
  }

  return (
    <div className="relative w-full min-w-0">
      <input className={`app-input pl-11 ${className}`.trim()} {...props} />
      <FontAwesomeIcon icon={faSearch} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[color:var(--textSecondary)]" />
      <button
        type="button"
        onClick={onSearch}
        className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md px-2.5 py-1.5 text-[color:var(--color-text)] hover:bg-white/10"
        aria-label={searchAriaLabel}
      >
        <FontAwesomeIcon icon={faSearch} className="w-3.5" />
      </button>
    </div>
  );
};

export default AppInput;
