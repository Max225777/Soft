import { useState, useEffect, useRef } from 'react'
import { api, type Me } from './api'
import BottomNav, { type Tab } from './components/BottomNav'
import Shop from './pages/Shop'
import Profile from './pages/Profile'
import Balance from './pages/Balance'
import Admin from './pages/Admin'
import Boost from './pages/Boost'
import type { Lang } from './i18n'
import { getT } from './i18n'

const LANG_KEY = 'lemur_lang'
const CHANNEL = 'LEMUR_SHOP'
const CHANNEL_URL = `https://t.me/${CHANNEL}`

export default function App() {
  const [tab, setTab]         = useState<Tab>('shop')
  const [me, setMe]           = useState<Me | null>(null)
  const [lang, setLang]       = useState<Lang>(() => (localStorage.getItem(LANG_KEY) as Lang) || 'ru')
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
  }, [lang])

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

  function selectLang(l: Lang) {
    localStorage.setItem(LANG_KEY, l)
    setLang(l)
    api.setLang(l).catch(() => {})
    refreshMe()
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

  if (subChecked && !subscribed) {
    return <SubGate lang={lang} onCheck={recheckSub} checking={checkingAgain} />
  }

  return (
    <>
      <div style={{ flex: 1 }}>
        {tab === 'shop'    && <Shop    key="shop"    lang={lang} me={me} onGoToBalance={() => setTab('balance')} onBuy={refreshMe} />}
        {tab === 'profile' && <Profile key="profile" me={me} lang={lang} onChangeLang={l => { setLang(l); refreshMe() }} />}
        {tab === 'balance' && <Balance key="balance" me={me} lang={lang} balanceDiff={balanceDiff} />}
        {tab === 'boost'   && <Boost   key="boost"   me={me} lang={lang} onRefresh={refreshMe} />}
        {tab === 'admin'   && <Admin   key="admin" />}
      </div>
      <BottomNav
        active={tab} onChange={setTab} lang={lang}
        isAdmin={me?.is_admin}
        showBoost={me?.is_admin || !me?.preview_mode}
      />
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

