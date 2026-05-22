import { useState, useEffect } from 'react'
import { api, type Category, type BuyResult, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import LegalFooter from '../components/LegalFooter'

interface Props { lang: Lang; me: Me | null; onGoToBalance: () => void }

type View = 'menu' | 'list' | 'buying' | 'success' | 'error' | 'stars'

function localPrice(stars: number, usd: number): JSX.Element {
  return (
    <>
      <span style={{ fontWeight: 800 }}>⭐{stars}</span>
      <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 12, marginLeft: 6 }}>(${usd.toFixed(2)})</span>
    </>
  )
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

        <div style={{
          background: 'rgba(0,0,0,.25)', borderRadius: 14,
          border: '1px solid var(--border)', padding: '14px 16px', marginBottom: 20,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontWeight: 700, fontSize: 15 }}>{T.final_price}</span>
          <span style={{ fontWeight: 800, fontSize: 24, color: 'var(--orange)' }}>
            ⭐{cat.price_stars}
            <span style={{ fontWeight: 400, fontSize: 13, color: 'var(--muted)', marginLeft: 8 }}>(${cat.price_usd.toFixed(2)})</span>
          </span>
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
  if (view === 'menu') {
    const starsBalance = me?.balance_stars ?? 0
    const usdDisplay = (starsBalance * 0.013).toFixed(2)

    return (
      <div className="page">
        {/* Hero card */}
        <div style={{
          background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
          border: '1px solid rgba(255,107,43,.22)',
          borderRadius: 20,
          padding: '20px 18px',
          marginBottom: 14,
          position: 'relative',
          overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: -30, right: -30,
            width: 150, height: 150, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(255,107,43,.12) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />

          <div>
            <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: 1, marginBottom: 4 }}>
              {T.balance.toUpperCase()}
            </div>
            <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1 }}>
              <span style={{ fontWeight: 800, fontSize: 30 }}>⭐{starsBalance}</span>
              <span style={{ fontWeight: 400, fontSize: 13, marginLeft: 7, color: 'var(--muted)' }}>(${usdDisplay})</span>
            </div>
          </div>
        </div>

        <h1 style={{ marginBottom: 14, fontSize: 19 }}>{T.shop}</h1>

        <div
          style={{
            background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
            border: '1px solid rgba(42,171,238,.2)',
            borderRadius: 16, padding: '20px 16px',
            display: 'flex', alignItems: 'center', gap: 16,
            cursor: 'pointer', marginBottom: 10,
            boxShadow: '0 4px 20px rgba(42,171,238,.1)',
          }}
          onClick={() => setView('list')}
        >
          <div className="cat-icon" style={{ background: 'linear-gradient(135deg, #2AABEE, #1178B8)', color: '#fff' }}>
            {TG_ICON}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_accounts}</div>
            <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{T.tg_accounts_desc}</div>
          </div>
          <div style={{ color: '#2AABEE', fontSize: 24, fontWeight: 300 }}>›</div>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, #0e1a0e 0%, #0a140a 100%)',
          border: '1px solid rgba(95,186,71,.12)',
          borderRadius: 16, padding: '20px 16px',
          display: 'flex', alignItems: 'center', gap: 16,
          opacity: 0.5,
        }}>
          <div className="cat-icon" style={{ background: 'linear-gradient(135deg, #5FBA47, #3a8a28)', color: '#fff', fontSize: 30 }}>👥</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_boost}</div>
            <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{T.tg_boost_desc}</div>
          </div>
          <span className="badge badge-orange" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{T.in_dev}</span>
        </div>
      <LegalFooter />
    </div>
    )
  }

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <button
            onClick={() => setView('menu')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--orange)', fontSize: 26, lineHeight: 1 }}
          >‹</button>
          <h1 style={{ margin: 0 }}>{T.tg_accounts}</h1>
        </div>

        {/* How-it-works banner */}
        <div style={{
          background: 'linear-gradient(135deg, #1E1428 0%, #141018 100%)',
          border: '1px solid rgba(255,107,43,.2)',
          borderRadius: 16,
          padding: '14px 16px',
          marginBottom: 14,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', letterSpacing: 1, marginBottom: 12 }}>
            {T.how_it_works.toUpperCase()}
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
            {T.how_steps.map((step, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', flex: 1 }}>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: 12,
                    background: i === T.how_steps.length - 1
                      ? 'linear-gradient(135deg, rgba(255,107,43,.3), rgba(255,107,43,.1))'
                      : 'rgba(255,255,255,.06)',
                    border: i === T.how_steps.length - 1
                      ? '1px solid rgba(255,107,43,.4)'
                      : '1px solid rgba(255,255,255,.08)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 18, marginBottom: 6, flexShrink: 0,
                  }}>
                    {step.icon}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text2)', lineHeight: 1.35, fontWeight: 500 }}>
                    {step.text}
                  </div>
                </div>
                {i < T.how_steps.length - 1 && (
                  <div style={{ color: 'var(--orange)', fontSize: 16, fontWeight: 300, marginTop: 10, flexShrink: 0, padding: '0 2px' }}>›</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {cats.length === 0 ? (
          <>
            <div className="card"><div className="skeleton" style={{ height: 80 }} /></div>
            <div className="card"><div className="skeleton" style={{ height: 80 }} /></div>
          </>
        ) : (
          cats.map(cat => {
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
                  <div className="price-pill" style={{ flex: 1, justifyContent: 'center', fontSize: 15, padding: '9px 12px' }}>
                    {localPrice(cat.price_stars, cat.price_usd)}
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

  // ─── Зірки ────────────────────────────────────────────────────────────────

  return null
}

const STAR_PACKAGES = [
  { stars: 50,   usd: 1.00 },
  { stars: 100,  usd: 2.00 },
  { stars: 250,  usd: 4.50 },
  { stars: 500,  usd: 8.50 },
  { stars: 1000, usd: 16.00 },
]

function StarsView({ me, lang, onBack }: { me: Me | null; lang: Lang; onBack(): void }) {
  const T = getT(lang)
  const [buying, setBuying] = useState<number | null>(null)
  const [done, setDone] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const rate = me?.rate_uah || 40

  async function buyStars(pkg: typeof STAR_PACKAGES[0]) {
    setBuying(pkg.stars); setErr(null)
    try {
      await api.starsBuy(pkg.stars, pkg.usd)
      setDone(pkg.stars)
    } catch (e: any) { setErr(e.message ?? 'Error') }
    finally { setBuying(null) }
  }

  return (
    <div className="page">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <button onClick={onBack} style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 22, cursor: 'pointer', padding: 0 }}>‹</button>
        <h1 style={{ margin: 0 }}>⭐ {T.tg_stars}</h1>
      </div>

      {done && (
        <div style={{ background: 'rgba(255,184,48,.1)', border: '1px solid rgba(255,184,48,.3)', borderRadius: 14, padding: '16px', marginBottom: 16, textAlign: 'center' }}>
          <div style={{ fontSize: 32, marginBottom: 6 }}>✅</div>
          <div style={{ fontWeight: 700 }}>
            {lang === 'ru' ? `Заказ на ${done} ⭐ принят!` : lang === 'ua' ? `Замовлення на ${done} ⭐ прийнято!` : `Order for ${done} ⭐ accepted!`}
          </div>
          <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>
            {lang === 'ru' ? 'Звёзды будут отправлены в течение 10 минут' : lang === 'ua' ? 'Зірки будуть відправлені протягом 10 хвилин' : 'Stars will be delivered within 10 minutes'}
          </div>
        </div>
      )}

      {err && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{err}</div>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {STAR_PACKAGES.map(pkg => {
          const uah = Math.round(pkg.usd * rate)
          const perStar = Math.round(uah / pkg.stars * 10) / 10
          return (
            <div key={pkg.stars} style={{
              background: 'linear-gradient(135deg, #1a180a 0%, #1a1600 100%)',
              border: '1px solid rgba(255,215,0,.2)',
              borderRadius: 14, padding: '14px 16px',
              display: 'flex', alignItems: 'center', gap: 14,
            }}>
              <div style={{
                width: 48, height: 48, borderRadius: 14, flexShrink: 0,
                background: 'rgba(255,215,0,.15)', border: '1px solid rgba(255,215,0,.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 800, fontSize: 16, color: '#FFD700',
              }}>
                {pkg.stars >= 1000 ? `${pkg.stars/1000}K` : pkg.stars}⭐
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{pkg.stars} Stars</div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                  {perStar} {lang === 'ru' ? 'грн/звезда' : lang === 'ua' ? 'грн/зірка' : '₴/star'}
                </div>
              </div>
              <button
                className="btn btn-primary"
                style={{ width: 'auto', padding: '9px 14px', fontSize: 13, background: 'linear-gradient(135deg, #FFB830, #e09000)' }}
                disabled={buying === pkg.stars || (me?.balance_usd ?? 0) < pkg.usd}
                onClick={() => buyStars(pkg)}
              >
                {buying === pkg.stars ? '⏳' : me && me.rate_uah ? `${uah}₴` : `$${pkg.usd.toFixed(2)}`}
              </button>
            </div>
          )
        })}
      </div>

      <div style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', marginTop: 16, padding: '0 8px', lineHeight: 1.6 }}>
        {lang === 'ru'
          ? '⚡ Звёзды отправляются на ваш Telegram аккаунт в течение 10 минут'
          : lang === 'ua'
          ? '⚡ Зірки відправляються на ваш Telegram акаунт протягом 10 хвилин'
          : '⚡ Stars are sent to your Telegram account within 10 minutes'}
      </div>
      <LegalFooter />
    </div>
  )
}
