import React from 'react';

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onRetry }) => {
  return (
    <div className="ds-panel p-8 text-center">
      <div className="space-y-4">
        <div className="text-6xl">⚠️</div>
        <h2 className="text-primary text-xl font-bold">Error</h2>
        <p className="text-danger">{message}</p>
        {onRetry && (
          <button onClick={onRetry} className="app-button-secondary mt-4">
            Try Again
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorMessage;
