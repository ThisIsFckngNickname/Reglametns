import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

async function startApp() {
  // Start MSW if enabled
  if (import.meta.env.VITE_USE_MSW === 'true') {
    const { worker } = await import('./mocks/browser')
    await worker.start({
      onUnhandledRequest: 'bypass',
      quiet: false,
    })
    console.log('[MSW] Mock Service Worker started')
  }

  const rootElement = document.getElementById('root')
  if (!rootElement) {
    throw new Error('Root element not found')
  }

  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
}

startApp()
