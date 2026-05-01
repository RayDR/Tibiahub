import React from 'react';

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onRetry }) => {
  return (
    <div className="tibia-panel p-8 text-center">
      <div className="space-y-4">
        <div className="text-6xl">⚠️</div>
        <h2 className="text-tibia-gold text-xl font-bold">Error</h2>
        <p className="text-red-400">{message}</p>
        {onRetry && (
          <button onClick={onRetry} className="tibia-button mt-4">
            Try Again
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorMessage;
