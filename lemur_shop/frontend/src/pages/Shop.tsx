import { useState, useEffect } from 'react'
import { api, type Category, type BuyResult, type Me } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang; me: Me | null; onGoToBalance: () => void }

type View = 'menu' | 'list' | 'buying' | 'success' | 'error'

function localPrice(usd: number, lang: Lang, me: Me | null): string {
  const base = `$${usd.toFixed(2)}`
  if (!me) return base
  if (lang === 'ua' && me.rate_uah) return `${base} (~${Math.round(usd * me.rate_uah)}₴)`
  if (lang === 'ru' && me.rate_rub) return `${base} (~${Math.round(usd * me.rate_rub)}₽)`
  return base
}

const TG_ICON = (
  <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.16 13.67l-2.965-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.993.889z"/>
  </svg>
)

export default function Shop({ lang, me, onGoToBalance }: Props) {
  const T = getT(lang)
  const [view, setView]     = useState<View>('menu')
  const [cats, setCats]     = useState<Category[]>([])
  const [result, setResult] = useState<BuyResult | null>(null)
  const [errMsg, setErr]    = useState('')
  const [copied, setCopied] = useState<'phone' | 'code' | ''>('')

  useEffect(() => {
    api.categories().catch(() => []).then(setCats)
  }, [])

  async function buy(cat: Category) {
    setView('buying')
    try {
      const res = await api.buy(cat.category)
      setResult(res)
      setView('success')
    } catch (e: any) {
      if (e.message === 'insufficient_balance') {
        setView('list')
        onGoToBalance()
        return
      }
      setErr(e.message ?? T.buy_error)
      setView('error')
    }
  }

  function copy(text: string, which: 'phone' | 'code') {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(which)
      setTimeout(() => setCopied(''), 2000)
    })
  }

  // ─── Головне меню магазину ─────────────────────────────────────────────────
  if (view === 'menu') return (
    <div className="page">
      <h1 style={{ marginBottom: 20 }}>{T.shop}</h1>

      {/* TG Акаунти — активний */}
      <div
        className="card"
        style={{ display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer', padding: '18px 16px' }}
        onClick={() => setView('list')}
      >
        <div style={{
          width: 64, height: 64, borderRadius: 16,
          background: 'linear-gradient(135deg, #2AABEE, #229ED9)',
          color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          {TG_ICON}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 17 }}>{T.tg_accounts}</div>
          <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>{T.tg_accounts_desc}</div>
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 22 }}>›</div>
      </div>

      {/* Telegram Stars — заглушка */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 16, opacity: 0.5, padding: '18px 16px' }}>
        <div style={{
          width: 64, height: 64, borderRadius: 16,
          background: 'linear-gradient(135deg, #FFD700, #FFA500)',
          color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, fontSize: 32,
        }}>
          ⭐
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 17 }}>{T.tg_stars}</div>
          <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>{T.tg_stars_desc}</div>
        </div>
        <span className="badge badge-orange" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{T.in_dev}</span>
      </div>

      {/* Накрутка — заглушка */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 16, opacity: 0.5, padding: '18px 16px' }}>
        <div style={{
          width: 64, height: 64, borderRadius: 16,
          background: 'linear-gradient(135deg, #7A9E5F, #5a7a42)',
          color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0, fontSize: 32,
        }}>
          👥
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 17 }}>{T.tg_boost}</div>
          <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>{T.tg_boost_desc}</div>
        </div>
        <span className="badge badge-orange" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{T.in_dev}</span>
      </div>
    </div>
  )

  // ─── Список країн ──────────────────────────────────────────────────────────
  if (view === 'list') return (
    <div className="page">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <button
          onClick={() => setView('menu')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--orange)', fontSize: 22 }}
        >‹</button>
        <h1 style={{ margin: 0 }}>{T.tg_accounts}</h1>
      </div>

      {cats.length === 0 ? (
        <>
          <div className="card"><div className="skeleton" style={{ height: 60 }} /></div>
          <div className="card"><div className="skeleton" style={{ height: 60 }} /></div>
        </>
      ) : (
        cats.map(cat => (
          <div key={cat.category} className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 32, flexShrink: 0 }}>{cat.flag}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{cat.title}</div>
              <div style={{ fontWeight: 700, color: 'var(--orange)', fontSize: 14, marginTop: 2 }}>
                {localPrice(cat.price_usd, lang, me)}
              </div>
            </div>
            <button
              className="btn btn-primary"
              style={{ padding: '8px 16px', width: 'auto', fontSize: 14 }}
              onClick={() => buy(cat)}
            >
              {T.buy}
            </button>
          </div>
        ))
      )}
    </div>
  )

  // ─── Купую ─────────────────────────────────────────────────────────────────
  if (view === 'buying') return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
      <div style={{ fontSize: 48 }}>🦎</div>
      <p style={{ fontWeight: 600, fontSize: 16 }}>{T.buying}</p>
    </div>
  )

  // ─── Успіх ─────────────────────────────────────────────────────────────────
  if (view === 'success' && result) return (
    <div className="page">
      <div className="card" style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 36, marginBottom: 6 }}>✅</div>
        <div style={{ fontWeight: 700, fontSize: 15 }}>
          {T.order_num} #{String(result.order_id).padStart(5, '0')}
        </div>
      </div>

      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>{T.your_phone}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{ flex: 1, fontSize: 18, fontWeight: 700 }}>{result.phone}</code>
          <button className="btn btn-secondary" style={{ width: 'auto', padding: '7px 12px' }}
            onClick={() => copy(result.phone, 'phone')}>
            {copied === 'phone' ? T.copied : T.copy}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>{T.your_code}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{ flex: 1, fontSize: 22, fontWeight: 700, letterSpacing: 3 }}>{result.code}</code>
          <button className="btn btn-secondary" style={{ width: 'auto', padding: '7px 12px' }}
            onClick={() => copy(result.code, 'code')}>
            {copied === 'code' ? T.copied : T.copy}
          </button>
        </div>
      </div>

      <div className="card" style={{ background: 'var(--sand)' }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>📋 {T.instruction}</div>
        <ol style={{ paddingLeft: 18, lineHeight: 2, margin: 0 }}>
          <li>{T.step1} <a href="https://justrunmy.app/panel/add" target="_blank" rel="noreferrer" style={{ color: 'var(--orange)' }}>justrunmy.app</a></li>
          <li>{T.step2}: <code>{result.phone}</code></li>
          <li>{T.step3}: <code>{result.code}</code></li>
          <li>{T.step4}</li>
        </ol>
        <p style={{ marginTop: 10, color: 'var(--brown)', fontSize: 12 }}>{T.warning}</p>
      </div>

      <button className="btn btn-secondary" onClick={() => { setResult(null); setView('menu') }}>
        {T.back}
      </button>
    </div>
  )

  // ─── Помилка ───────────────────────────────────────────────────────────────
  if (view === 'error') return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
      <div style={{ fontSize: 48 }}>❌</div>
      <p style={{ fontWeight: 600 }}>{errMsg || T.buy_error}</p>
      <button className="btn btn-secondary" onClick={() => setView('list')}>{T.back}</button>
    </div>
  )

  return null
}
