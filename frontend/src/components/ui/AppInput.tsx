import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSearch, faXmark } from '@fortawesome/free-solid-svg-icons';

interface AppInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  search?: boolean;
  onSearch?: () => void;
  onClear?: () => void;
  showClear?: boolean;
  searchAriaLabel?: string;
  clearAriaLabel?: string;
}

const AppInput: React.FC<AppInputProps> = ({
  search = false,
  onSearch,
  onClear,
  showClear = false,
  searchAriaLabel = 'Search',
  clearAriaLabel = 'Clear search',
  className = '',
  ...props
}) => {
  if (!search) {
    return <input className={`app-input ${className}`.trim()} {...props} />;
  }

  return (
    <div className="relative w-full min-w-0">
      <input className={`app-input pr-20 ${className}`.trim()} {...props} />
      {showClear && (
        <button
          type="button"
          onClick={onClear}
          className="absolute right-12 top-1/2 -translate-y-1/2 rounded-md px-2 py-1.5 text-[color:var(--color-text-muted)] hover:bg-white/10 hover:text-[color:var(--color-text)]"
          aria-label={clearAriaLabel}
        >
          <FontAwesomeIcon icon={faXmark} className="w-3.5" />
        </button>
      )}
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
