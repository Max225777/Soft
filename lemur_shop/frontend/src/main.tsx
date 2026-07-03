import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { err: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { err: false }
  }
  static getDerivedStateFromError() {
    return { err: true }
  }
  componentDidCatch(error: unknown) {
    try { console.error('App crashed:', error) } catch { /* ignore */ }
  }
  render() {
    if (this.state.err) {
      return (
        <div style={{
          position: 'fixed', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 16, padding: 28, textAlign: 'center',
          background: 'linear-gradient(160deg, #1E1428 0%, #0C0C10 100%)', color: '#fff',
        }}>
          <div style={{ fontSize: 52 }}>🦎</div>
          <div style={{ fontWeight: 800, fontSize: 17 }}>Что-то пошло не так</div>
          <div style={{ fontSize: 13, color: '#b9b4c2', maxWidth: 300, lineHeight: 1.5 }}>
            Приложение не смогло отобразиться. Попробуйте обновить.
          </div>
          <button
            onClick={() => location.reload()}
            style={{
              background: 'linear-gradient(135deg, #FF6B2B, #E8530A)', color: '#fff',
              border: 'none', borderRadius: 12, padding: '12px 24px', fontSize: 15, fontWeight: 700, cursor: 'pointer',
            }}
          >Обновить</button>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><ErrorBoundary><App /></ErrorBoundary></React.StrictMode>
)
