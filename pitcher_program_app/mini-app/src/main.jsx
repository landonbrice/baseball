import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

async function bootstrap() {
  // Backend-less dev mode: when VITE_USE_MOCKS=true, start the MSW worker
  // before first render so every /api/* call is served from fixtures. The
  // dynamic import keeps MSW out of the production bundle entirely.
  if (import.meta.env.VITE_USE_MOCKS === 'true') {
    const { worker } = await import('./mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
    console.info('[mini-app] MSW mock backend active (VITE_USE_MOCKS=true) — no real backend in use')
  }

  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}

bootstrap()
