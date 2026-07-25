import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import './i18n';
import ErrorBoundary from './components/ErrorBoundary';

import { BrowserRouter } from 'react-router-dom';
import { AppearanceProvider, initializeAppearance } from './context/AppearanceContext';

const initialAppearance = initializeAppearance();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppearanceProvider initialPreferences={initialAppearance}>
      <ErrorBoundary>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ErrorBoundary>
    </AppearanceProvider>
  </StrictMode>,
)
