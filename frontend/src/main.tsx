import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import './i18n';
import ErrorBoundary from './components/ErrorBoundary';

import { BrowserRouter } from 'react-router-dom';
import { MotionConfig } from 'framer-motion';
import { AppearanceProvider, initializeAppearance, useAppearance } from './context/AppearanceContext';

const initialAppearance = initializeAppearance();

function MotionBoundary({ children }: { children: React.ReactNode }) {
  const { motion } = useAppearance();
  return <MotionConfig reducedMotion={motion === 'reduced' ? 'always' : 'user'}>{children}</MotionConfig>;
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppearanceProvider initialPreferences={initialAppearance}>
      <MotionBoundary>
        <ErrorBoundary>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ErrorBoundary>
      </MotionBoundary>
    </AppearanceProvider>
  </StrictMode>,
)
