import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.jsx'
import { ToastProvider } from './components/ToastContext'
import { ThemeProvider } from './components/ThemeContext'
import { SSEProvider } from './hooks/useSSE'
import { ErrorBoundary } from './components/ErrorBoundary'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60, // 1 minute
    }
  }
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {/* ErrorBoundary is outermost so a throw anywhere (including in a provider)
        can never unmount the whole tree into a blank page.
        BrowserRouter must sit ABOVE ToastProvider: toasts render <Link>, and a
        <Link> outside a Router throws — which is exactly what blanked the app
        every time a new alert fired a "SAR ready" toast. */}
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ThemeProvider>
            <ToastProvider>
              {/* One shared EventSource for the whole app (see hooks/useSSE). */}
              <SSEProvider>
                <App />
              </SSEProvider>
            </ToastProvider>
          </ThemeProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)

