import { useState, useEffect } from 'react'
import { api, type Category, type BuyResult, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import { getLevel, getLevelIdx, LEVELS } from './Profile'

interface Props { lang: Lang; me: Me | null; onGoToBalance: () => void }

type View = 'menu' | 'list' | 'buying' | 'success' | 'error'

function localPrice(usd: number, lang: Lang, me: Me | null): JSX.Element {
  const usdSpan = <span style={{ fontWeight: 400, color: 'var(--muted)' }}>(${usd.toFixed(2)})</span>
  if (!me) return <span style={{ fontWeight: 700 }}>${usd.toFixed(2)}</span>
  if (lang === 'ua' && me.rate_uah) return <><span style={{ fontWeight: 700 }}>{Math.round(usd * me.rate_uah)}₴</span> {usdSpan}</>
  if (lang === 'ru' && me.rate_rub) return <><span style={{ fontWeight: 700 }}>{Math.round(usd * me.rate_rub)}₽</span> {usdSpan}</>
  return <span style={{ fontWeight: 700 }}>${usd.toFixed(2)}</span>
}

function discountedPrice(base: number, pct: number) {
  return Math.round(base * (100 - pct) * 100) / 10000
}

const TG_ICON = (
  <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.16 13.67l-2.965-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.993.889z"/>
  </svg>
)

interface ConfirmProps {
  cat: Category; me: Me | null; lang: Lang
  onConfirm(): void; onCancel(): void
}

function ConfirmModal({ cat, me, lang, onConfirm, onCancel }: ConfirmProps) {
  const T = getT(lang)
  const spent = me?.total_spent_usd ?? 0
  const lvl = getLevel(spent)
  const lvlIdx = getLevelIdx(spent)
  const discount = lvl.discount
  const finalUsd = discountedPrice(cat.price_usd, discount)

  function fmtPrice(usd: number) {
    if (!me) return `$${usd.toFixed(2)}`
    if (lang === 'ua' && me.rate_uah) return `${Math.round(usd * me.rate_uah)}₴ ($${usd.toFixed(2)})`
    if (lang === 'ru' && me.rate_rub) return `${Math.round(usd * me.rate_rub)}₽ ($${usd.toFixed(2)})`
    return `$${usd.toFixed(2)}`
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,.75)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
      backdropFilter: 'blur(6px)',
    }} onClick={onCancel}>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 480,
          background: 'linear-gradient(160deg, #1E1428 0%, #141018 100%)',
          border: '1px solid rgba(255,107,43,.25)',
          borderRadius: '24px 24px 0 0',
          padding: '20px 20px 32px',
        }}
      >
        <div style={{ width: 40, height: 4, borderRadius: 4, background: 'rgba(255,255,255,.15)', margin: '0 auto 20px' }} />

        <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 4 }}>{T.confirm_buy}</div>
        <div className="muted" style={{ fontSize: 13, marginBottom: 18 }}>{T.confirm_desc}</div>

        {/* Product */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 14,
          background: 'rgba(255,255,255,.04)', border: '1px solid var(--border)',
          borderRadius: 14, padding: '14px 16px', marginBottom: 16,
        }}>
          <div style={{ fontSize: 38, lineHeight: 1 }}>{cat.flag}</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>{cat.title}</div>
            <div className="muted" style={{ fontSize: 12 }}>Telegram account</div>
          </div>
        </div>

        {/* Price breakdown */}
        <div style={{
          background: 'rgba(0,0,0,.25)', borderRadius: 14,
          border: '1px solid var(--border)', padding: '14px 16px', marginBottom: 16,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span className="muted" style={{ fontSize: 13 }}>{T.original_price}</span>
            <span style={{ fontWeight: 600, fontSize: 14, textDecoration: 'line-through', color: 'var(--muted)' }}>
              {fmtPrice(cat.price_usd)}
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="muted" style={{ fontSize: 13 }}>{T.your_discount}</span>
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
                background: `${lvl.color}20`, color: lvl.color, border: `1px solid ${lvl.color}35`,
              }}>
                {lvl.icon} −{discount}%
              </span>
            </div>
            <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--green)' }}>−{fmtPrice(cat.price_usd - finalUsd)}</span>
          </div>

          <div style={{ height: 1, background: 'var(--border)', marginBottom: 12 }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>{T.final_price}</span>
            <span style={{ fontWeight: 800, fontSize: 22, color: 'var(--orange)' }}>
              {fmtPrice(finalUsd)}
            </span>
          </div>
        </div>

        {/* Level progress dots */}
        <div style={{ display: 'flex', gap: 5, marginBottom: 20 }}>
          {LEVELS.map((l, i) => (
            <div key={i} style={{ flex: 1, textAlign: 'center' }}>
              <div style={{
                height: 3, borderRadius: 3, marginBottom: 4,
                background: i <= lvlIdx ? l.color : 'rgba(255,255,255,.08)',
                boxShadow: i <= lvlIdx ? `0 0 6px ${l.glow}` : 'none',
              }} />
              <div style={{ fontSize: 14 }}>{l.icon}</div>
              <div style={{ fontSize: 9, color: i === lvlIdx ? l.color : 'var(--muted)', fontWeight: 700, marginTop: 2 }}>
                −{l.discount}%
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onCancel}>{T.cancel}</button>
          <button className="btn btn-primary" style={{ flex: 2 }} onClick={onConfirm}>{T.confirm}</button>
        </div>
      </div>
    </div>
  )
}

export default function Shop({ lang, me, onGoToBalance }: Props) {
  const T = getT(lang)
  const [view, setView]       = useState<View>('menu')
  const [cats, setCats]       = useState<Category[]>([])
  const [result, setResult]   = useState<BuyResult | null>(null)
  const [errMsg, setErr]      = useState('')
  const [code, setCode]       = useState('')
  const [gettingCode, setGettingCode] = useState(false)
  const [copied, setCopied]   = useState<'phone' | 'code' | ''>('')
  const [confirmCat, setConfirmCat] = useState<Category | null>(null)

  useEffect(() => {
    api.categories().catch(() => []).then(setCats)
  }, [])

  async function buy(cat: Category) {
    setConfirmCat(null)
    setView('buying')
    setCode('')
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

  async function getCode() {
    if (!result) return
    setGettingCode(true)
    try {
      const res = await api.getCode(result.order_id)
      setCode(res.code)
    } catch (e: any) {
      setCode('❌ ' + (e.message ?? 'error'))
    } finally {
      setGettingCode(false)
    }
  }

  function copy(text: string, which: 'phone' | 'code') {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(which)
      setTimeout(() => setCopied(''), 2000)
    })
  }

  // ─── Головне меню ─────────────────────────────────────────────────────────
  if (view === 'menu') return (
    <div className="page">
      <h1 style={{ marginBottom: 18 }}>{T.shop}</h1>

      <div
        className="card"
        style={{ display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer', padding: '22px 16px' }}
        onClick={() => setView('list')}
      >
        <div className="cat-icon" style={{ background: 'linear-gradient(135deg, #2AABEE, #1178B8)', color: '#fff' }}>
          {TG_ICON}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_accounts}</div>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{T.tg_accounts_desc}</div>
        </div>
        <div style={{ color: 'var(--orange2)', fontSize: 24, fontWeight: 300 }}>›</div>
      </div>

      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 16, opacity: 0.45, padding: '22px 16px' }}>
        <div className="cat-icon" style={{ background: 'linear-gradient(135deg, #FFD700, #E8950A)', color: '#fff', fontSize: 30 }}>⭐</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_stars}</div>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{T.tg_stars_desc}</div>
        </div>
        <span className="badge badge-orange" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{T.in_dev}</span>
      </div>

      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 16, opacity: 0.45, padding: '22px 16px' }}>
        <div className="cat-icon" style={{ background: 'linear-gradient(135deg, #5FBA47, #3a8a28)', color: '#fff', fontSize: 30 }}>👥</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_boost}</div>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{T.tg_boost_desc}</div>
        </div>
        <span className="badge badge-orange" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{T.in_dev}</span>
      </div>
    </div>
  )

  // ─── Список ───────────────────────────────────────────────────────────────
  if (view === 'list') return (
    <>
      {confirmCat && (
        <ConfirmModal
          cat={confirmCat} me={me} lang={lang}
          onConfirm={() => buy(confirmCat)}
          onCancel={() => setConfirmCat(null)}
        />
      )}
      <div className="page">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <button
            onClick={() => setView('menu')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--orange)', fontSize: 26, lineHeight: 1 }}
          >‹</button>
          <h1 style={{ margin: 0 }}>{T.tg_accounts}</h1>
        </div>

        {cats.length === 0 ? (
          <>
            <div className="card"><div className="skeleton" style={{ height: 80 }} /></div>
            <div className="card"><div className="skeleton" style={{ height: 80 }} /></div>
          </>
        ) : (
          cats.map(cat => {
            const spent = me?.total_spent_usd ?? 0
            const discount = getLevel(spent).discount
            const finalUsd = discountedPrice(cat.price_usd, discount)
            return (
              <div key={cat.category} className="card" style={{ padding: '20px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
                  <div style={{ fontSize: 44, flexShrink: 0, lineHeight: 1 }}>{cat.flag}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 800, fontSize: 17 }}>{cat.title}</div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>Telegram account</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="price-pill" style={{ flex: 1, justifyContent: 'center', flexDirection: 'column', fontSize: 15, padding: '9px 12px', gap: 2 }}>
                    <span>{localPrice(finalUsd, lang, me)}</span>
                    {discount > 0 && (
                      <span style={{ fontSize: 11, color: 'var(--muted)', textDecoration: 'line-through' }}>
                        ${cat.price_usd.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <button
                    className="btn btn-primary"
                    style={{ width: 'auto', padding: '10px 22px', fontSize: 15 }}
                    onClick={() => setConfirmCat(cat)}
                  >{T.buy}</button>
                </div>
              </div>
            )
          })
        )}
      </div>
    </>
  )

  // ─── Купую ─────────────────────────────────────────────────────────────────
  if (view === 'buying') return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
      <div style={{ fontSize: 48 }}>🦎</div>
      <p style={{ fontWeight: 600, fontSize: 16 }}>{T.buying}</p>
    </div>
  )

  // ─── Успіх ─────────────────────────────────────────────────────────────────
  if (view === 'success' && result) {
    const receivedAt = result.created_at
      ? new Date(result.created_at).toLocaleString(lang === 'en' ? 'en-GB' : lang === 'ua' ? 'uk-UA' : 'ru-RU',
          { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
      : ''

    return (
    <div className="page">
      <div className="card" style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 36, marginBottom: 6 }}>✅</div>
        <div style={{ fontWeight: 700, fontSize: 15 }}>
          {T.order_num} #{String(result.order_id).padStart(5, '0')}
        </div>
        {receivedAt && (
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{T.received_at}: {receivedAt}</div>
        )}
      </div>

      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{T.your_phone}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{ flex: 1, fontSize: 20, fontWeight: 700, letterSpacing: 1 }}>{result.phone}</code>
          <button className="btn btn-secondary" style={{ width: 'auto', padding: '7px 12px' }}
            onClick={() => copy(result.phone, 'phone')}>
            {copied === 'phone' ? T.copied : T.copy}
          </button>
        </div>
      </div>

      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 8 }}>📋 {T.instruction}</div>
        <ol style={{ paddingLeft: 18, lineHeight: 2, margin: 0 }}>
          <li>{T.step1}</li>
          <li>{T.step2}: <code>{result.phone}</code></li>
          <li>{T.step3}</li>
          <li>{T.step4}</li>
        </ol>
        <p style={{ marginTop: 10, fontSize: 12, color: 'var(--text2)' }}>{T.warning}</p>
      </div>

      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{T.your_code}</div>
        <button
          className="btn btn-primary"
          style={{ fontSize: 15, marginBottom: code ? 12 : 0 }}
          disabled={gettingCode}
          onClick={getCode}
        >
          {gettingCode ? T.getting_code : T.get_code}
        </button>
        {code && !code.startsWith('❌') && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
            <code style={{ flex: 1, fontSize: 28, fontWeight: 700, letterSpacing: 6 }}>{code}</code>
            <button className="btn btn-secondary" style={{ width: 'auto', padding: '7px 12px' }}
              onClick={() => copy(code, 'code')}>
              {copied === 'code' ? T.copied : T.copy}
            </button>
          </div>
        )}
        {code && code.startsWith('❌') && (
          <p style={{ color: '#e53', fontSize: 13, margin: '8px 0 0' }}>{code}</p>
        )}
      </div>

      <button className="btn btn-secondary" onClick={() => { setResult(null); setCode(''); setView('menu') }}>
        {T.back}
      </button>
    </div>
    )
  }

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
