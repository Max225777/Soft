import { useState, useEffect, useRef } from 'react'
import { api, type Me } from './api'
import BottomNav, { type Tab } from './components/BottomNav'
import Shop from './pages/Shop'
import Profile from './pages/Profile'
import Balance from './pages/Balance'
import Admin from './pages/Admin'
import Referral from './pages/Referral'
import Partner from './pages/Partner'
import Orders from './pages/Orders'
import type { Lang } from './i18n'

const LANG_KEY = 'lemur_lang'
const CHANNEL = 'LEMUR_SHOP'
const CHANNEL_URL = `https://t.me/${CHANNEL}`

export default function App() {
  const [tab, setTab]         = useState<Tab>('shop')
  const [me, setMe]           = useState<Me | null>(null)
  const [lang, setLang] = useState<Lang>(() => {
    const saved = localStorage.getItem(LANG_KEY) as Lang | null
    if (saved === 'ru' || saved === 'ua' || saved === 'en') return saved
    const tgLang = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code ?? ''
    if (tgLang.startsWith('uk')) return 'ua'
    if (tgLang.startsWith('en')) return 'en'
    return 'ru'
  })
  const [subChecked, setSubChecked] = useState(false)
  const [subscribed, setSubscribed] = useState(true)
  const [checkingAgain, setCheckingAgain] = useState(false)
  const [balanceDiff, setBalanceDiff] = useState<number | null>(null)
  const prevStars = useRef<number>(0)

  useEffect(() => {
    window.Telegram?.WebApp?.expand()
    api.me().then(u => { setMe(u); prevStars.current = u.balance_stars }).catch(() => {})
    api.checkSub().then(r => {
      setSubscribed(r.subscribed)
      setSubChecked(true)
    }).catch(() => {
      setSubscribed(true)
      setSubChecked(true)
    })
  }, [])

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const fresh = await api.me()
        const diff = fresh.balance_stars - prevStars.current
        if (diff > 0) {
          setBalanceDiff(diff)
          setTimeout(() => setBalanceDiff(null), 2500)
        }
        prevStars.current = fresh.balance_stars
        setMe(fresh)
      } catch {}
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  function refreshMe() { api.me().then(u => { prevStars.current = u.balance_stars; setMe(u) }).catch(() => {}) }

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

  if (subChecked && !subscribed) {
    return <SubGate lang={lang} onCheck={recheckSub} checking={checkingAgain} />
  }

  return (
    <>
      <Backdrop />
      <div style={{ flex: 1 }}>
        {tab === 'shop'     && <Shop     key="shop"     lang={lang} me={me} onGoToBalance={() => setTab('balance')} onGoToProfile={() => setTab('profile')} onBuy={refreshMe} />}
        {tab === 'profile'  && <Profile  key="profile"  me={me} lang={lang} onChangeLang={l => { setLang(l); localStorage.setItem(LANG_KEY, l); refreshMe() }} />}
        {tab === 'orders'   && <Orders   key="orders"   lang={lang} />}
        {tab === 'balance'  && <Balance  key="balance"  me={me} lang={lang} balanceDiff={balanceDiff} />}
        {tab === 'referral' && <Referral key="referral" lang={lang} botUsername={me?.bot_username ?? ''} />}
        {tab === 'partner'  && <Partner  key="partner"  lang={lang} me={me} />}
        {tab === 'admin'    && <Admin    key="admin" />}
      </div>
      <BottomNav active={tab} onChange={setTab} lang={lang} isAdmin={me?.is_admin} isPartner={me?.is_partner} />
    </>
  )
}

function Backdrop() {
  return (
    <div className="backdrop" aria-hidden="true">
      <div className="bd-glow bd-glow-1" />
      <div className="bd-glow bd-glow-2" />
      <div className="bd-cube bd-cube-1" />
      <div className="bd-cube bd-cube-2" />
      <svg className="bd-plane" viewBox="0 0 24 24" fill="currentColor">
        <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71l-4.14-3.05-1.99 1.93c-.23.23-.42.42-.83.42z"/>
      </svg>
    </div>
  )
}

function SubGate({ lang, onCheck, checking }: { lang: Lang; onCheck(): void; checking: boolean }) {
  const sub = {
    ua: { title: 'Підпишіться на канал', desc: 'Щоб користуватись магазином, підпишіться на наш офіційний канал', btn: '📢 Підписатись', check: '✅ Перевірити підписку' },
    ru: { title: 'Подпишитесь на канал', desc: 'Чтобы пользоваться магазином, подпишитесь на наш официальный канал', btn: '📢 Подписаться', check: '✅ Проверить подписку' },
    en: { title: 'Subscribe to the channel', desc: 'To use the shop, please subscribe to our official channel', btn: '📢 Subscribe', check: '✅ Check subscription' },
  }[lang]

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '100dvh', gap: 0, padding: 28,
      background: 'radial-gradient(ellipse at 50% -10%, rgba(46,124,246,.18) 0%, transparent 55%), #030304',
    }}>
      <div style={{ fontSize: 64, marginBottom: 12 }}>🦎</div>
      <div className="display" style={{ fontSize: 24, color: 'var(--text)', marginBottom: 8, textAlign: 'center' }}>
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
        background: 'rgba(46,124,246,.08)', border: '1px solid rgba(46,124,246,.25)',
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
