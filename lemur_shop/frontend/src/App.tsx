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
const CHANNEL = 'LEMUR_SHOP'
const CHANNEL_URL = `https://t.me/${CHANNEL}`

export default function App() {
  const [tab, setTab]         = useState<Tab>('shop')
  const [me, setMe]           = useState<Me | null>(null)
  const [lang, setLang]       = useState<Lang | null>(() => {
    const saved = localStorage.getItem(LANG_KEY)
    return (saved as Lang) || null
  })
  const [subChecked, setSubChecked] = useState(false)
  const [subscribed, setSubscribed] = useState(true)
  const [checkingAgain, setCheckingAgain] = useState(false)

  useEffect(() => {
    window.Telegram?.WebApp?.expand()
    if (lang) {
      api.me().then(setMe).catch(() => {})
      api.checkSub().then(r => {
        setSubscribed(r.subscribed)
        setSubChecked(true)
      }).catch(() => {
        setSubscribed(true)
        setSubChecked(true)
      })
    }
  }, [lang])

  function selectLang(l: Lang) {
    localStorage.setItem(LANG_KEY, l)
    setLang(l)
    api.setLang(l).catch(() => {})
    api.me().then(setMe).catch(() => {})
  }

  async function recheckSub() {
    setCheckingAgain(true)
    try {
      const r = await api.checkSub()
      setSubscribed(r.subscribed)
    } catch {
      setSubscribed(true)
    } finally {
      setCheckingAgain(false)
    }
  }

  if (!lang) return <LangSelect onSelect={selectLang} />

  if (lang && subChecked && !subscribed) {
    const T = getT(lang)
    return <SubGate lang={lang} onCheck={recheckSub} checking={checkingAgain} />
  }

  return (
    <>
      <div style={{ flex: 1 }}>
        {tab === 'shop'    && <Shop    key="shop"    lang={lang} me={me} onGoToBalance={() => setTab('balance')} />}
        {tab === 'profile' && <Profile key="profile" me={me} lang={lang} onChangeLang={l => { setLang(l); api.me().then(setMe).catch(() => {}) }} />}
        {tab === 'balance' && <Balance key="balance" me={me} lang={lang} onRefresh={() => api.me().then(setMe).catch(() => {})} />}
      </div>
      <BottomNav active={tab} onChange={setTab} lang={lang} />
    </>
  )
}

function SubGate({ lang, onCheck, checking }: { lang: Lang; onCheck(): void; checking: boolean }) {
  const T = getT(lang)
  const sub = {
    ua: { title: 'Підпишіться на канал', desc: 'Щоб користуватись магазином, підпишіться на наш офіційний канал', btn: '📢 Підписатись', check: '✅ Перевірити підписку' },
    ru: { title: 'Подпишитесь на канал', desc: 'Чтобы пользоваться магазином, подпишитесь на наш официальный канал', btn: '📢 Подписаться', check: '✅ Проверить подписку' },
    en: { title: 'Subscribe to the channel', desc: 'To use the shop, please subscribe to our official channel', btn: '📢 Subscribe', check: '✅ Check subscription' },
  }[lang]

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '100dvh', gap: 0, padding: 28,
      background: 'linear-gradient(160deg, #1E1428 0%, #0C0C10 100%)',
    }}>
      <div style={{ fontSize: 64, marginBottom: 12 }}>🦎</div>
      <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)', marginBottom: 8, textAlign: 'center' }}>
        Лемур
      </div>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', marginBottom: 6, textAlign: 'center' }}>
        {sub.title}
      </div>
      <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 28, textAlign: 'center', lineHeight: 1.5 }}>
        {sub.desc}
      </div>

      <div style={{
        width: '100%', maxWidth: 320,
        background: 'rgba(255,107,43,.08)', border: '1px solid rgba(255,107,43,.25)',
        borderRadius: 16, padding: '16px 20px', marginBottom: 20,
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: 14, flexShrink: 0,
          background: 'linear-gradient(135deg, #2AABEE, #1178B8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
        }}>📢</div>
        <div>
          <div style={{ fontWeight: 800, fontSize: 16 }}>@{CHANNEL}</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            {lang === 'ua' ? 'Офіційний канал' : lang === 'ru' ? 'Официальный канал' : 'Official channel'}
          </div>
        </div>
      </div>

      <div style={{ width: '100%', maxWidth: 320, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <a href={CHANNEL_URL} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
          <button className="btn btn-primary" style={{ width: '100%', fontSize: 15 }}>
            {sub.btn}
          </button>
        </a>
        <button
          className="btn btn-secondary"
          style={{ width: '100%', fontSize: 15 }}
          disabled={checking}
          onClick={onCheck}
        >
          {checking ? '⏳ ...' : sub.check}
        </button>
      </div>
    </div>
  )
}

function LangSelect({ onSelect }: { onSelect: (l: Lang) => void }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '100dvh', gap: 12, padding: 28,
    }}>
      <div style={{ fontSize: 56, marginBottom: 4 }}>🦎</div>
      <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--text)' }}>Лемур</div>
      <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 16, textAlign: 'center' }}>
        Виберіть мову · Choose language · Выберите язык
      </div>
      {(['ru', 'ua', 'en'] as const).map(l => (
        <button key={l} className="btn btn-primary" style={{ width: '100%', maxWidth: 300 }}
          onClick={() => onSelect(l)}>
          {l === 'ru' ? '🇷🇺 Русский' : l === 'ua' ? '🇺🇦 Українська' : '🇬🇧 English'}
        </button>
      ))}
    </div>
  )
}
