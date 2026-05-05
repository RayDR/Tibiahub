import React from 'react';

type ErrorBoundaryState = {
  hasError: boolean;
};

export default class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = {
    hasError: false,
  };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error): void {
    console.error('UI crash captured by ErrorBoundary:', error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center px-4">
          <div className="max-w-md rounded-xl border border-red-500/20 bg-red-950/20 p-6 text-center text-red-100">
            <h2 className="text-lg font-semibold mb-2">Something went wrong</h2>
            <p className="text-sm text-red-200/80 mb-4">The page crashed unexpectedly. Reload to recover.</p>
            <button
              onClick={() => window.location.reload()}
              className="rounded-md border border-red-400/30 bg-red-600/20 px-4 py-2 text-sm hover:bg-red-600/30"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
