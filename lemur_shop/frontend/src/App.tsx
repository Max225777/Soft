import { useState, useEffect } from 'react'
import { api, type Me } from './api'
import BottomNav from './components/BottomNav'
import Shop from './pages/Shop'
import Profile from './pages/Profile'
import Balance from './pages/Balance'
import type { Lang } from './i18n'
import { getT } from './i18n'

type Tab = 'shop' | 'profile' | 'balance'

const LANG_KEY = 'lemur_lang'

export default function App() {
  const [tab, setTab]   = useState<Tab>('shop')
  const [me, setMe]     = useState<Me | null>(null)
  const [lang, setLang] = useState<Lang | null>(() => {
    const saved = localStorage.getItem(LANG_KEY)
    return (saved as Lang) || null
  })

  useEffect(() => {
    window.Telegram?.WebApp?.expand()
    if (lang) {
      api.me().then(user => {
        setMe(user)
      }).catch(() => {})
    }
  }, [lang])

  function selectLang(l: Lang) {
    localStorage.setItem(LANG_KEY, l)
    setLang(l)
    api.setLang(l).catch(() => {})
    api.me().then(setMe).catch(() => {})
  }

  if (!lang) {
    return <LangSelect onSelect={selectLang} />
  }

  return (
    <>
      <div style={{ flex: 1 }}>
        {tab === 'shop'    && <Shop    lang={lang} me={me} />}
        {tab === 'profile' && <Profile me={me} lang={lang} onChangeLang={l => { setLang(l); api.me().then(setMe).catch(() => {}) }} />}
        {tab === 'balance' && <Balance me={me} lang={lang} />}
      </div>
      <BottomNav active={tab} onChange={setTab} lang={lang} />
    </>
  )
}

function LangSelect({ onSelect }: { onSelect: (l: Lang) => void }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', height: '100vh', gap: 16, padding: 24,
    }}>
      <div style={{ fontSize: 48 }}>🦎</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--brown)' }}>Лемур</div>
      <div style={{ fontSize: 14, color: 'var(--brown2)', marginBottom: 8 }}>
        Виберіть мову / Choose language / Выберите язык
      </div>
      <button className="btn btn-primary" style={{ width: '100%', maxWidth: 280 }}
        onClick={() => onSelect('ru')}>🇷🇺 Русский</button>
      <button className="btn btn-primary" style={{ width: '100%', maxWidth: 280 }}
        onClick={() => onSelect('ua')}>🇺🇦 Українська</button>
      <button className="btn btn-primary" style={{ width: '100%', maxWidth: 280 }}
        onClick={() => onSelect('en')}>🇬🇧 English</button>
    </div>
  )
}
