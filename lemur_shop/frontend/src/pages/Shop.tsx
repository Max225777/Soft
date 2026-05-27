import { useState, useEffect } from 'react'
import { api, smmApi, type Category, type BuyResult, type Me, type SmmService } from '../api'
import { getT, type Lang } from '../i18n'
import LegalFooter from '../components/LegalFooter'

interface Props { lang: Lang; me: Me | null; onGoToBalance: () => void; onBuy?: () => void }

type View = 'menu' | 'list' | 'buying' | 'success' | 'error' | 'stars' | 'smm'

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
          {cat.discount_stars ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ textDecoration: 'line-through', color: 'var(--muted)', fontSize: 16 }}>⭐{cat.price_stars}</span>
              <span style={{ fontWeight: 800, fontSize: 24, color: '#ff6b2b' }}>⭐{cat.discount_stars}</span>
            </span>
          ) : (
            <span style={{ fontWeight: 800, fontSize: 24, color: 'var(--orange)' }}>
              ⭐{cat.price_stars}
              <span style={{ fontWeight: 400, fontSize: 13, color: 'var(--muted)', marginLeft: 8 }}>(${cat.price_usd.toFixed(2)})</span>
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onCancel}>{T.cancel}</button>
          <button className="btn btn-primary" style={{ flex: 2 }} onClick={onConfirm}>{T.confirm}</button>
        </div>
      </div>
    </div>
  )
}

export default function Shop({ lang, me, onGoToBalance, onBuy }: Props) {
  const T = getT(lang)
  const [view, setView]       = useState<View>('menu')
  const [cats, setCats]       = useState<Category[]>([])
  const [result, setResult]   = useState<BuyResult | null>(null)
  const [errMsg, setErr]      = useState('')
  const [code, setCode]       = useState('')
  const [gettingCode, setGettingCode] = useState(false)
  const [copied, setCopied]   = useState<'phone' | 'code' | ''>('')
  const [confirmCat, setConfirmCat] = useState<Category | null>(null)
  const [smmServices, setSmmServices] = useState<SmmService[]>([])
  const [smmLink, setSmmLink] = useState('')
  const [smmQty, setSmmQty] = useState(100)
  const [smmCustom, setSmmCustom] = useState('')
  const [smmLoading, setSmmLoading] = useState(false)
  const [smmError, setSmmError] = useState<string | null>(null)
  const [smmDone, setSmmDone] = useState<{ order_id: number; stars_spent: number } | null>(null)

  useEffect(() => {
    api.categories().catch(() => []).then(setCats)
    smmApi.services().then(setSmmServices).catch(() => {})
  }, [])

  async function buy(cat: Category) {
    setConfirmCat(null)
    setView('buying')
    setCode('')
    try {
      const res = await api.buy(cat.category)
      setResult(res)
      setView('success')
      onBuy?.()
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

        <div
          style={{
            background: 'linear-gradient(135deg, #0e1a0e 0%, #0a140a 100%)',
            border: '1px solid rgba(95,186,71,.25)',
            borderRadius: 16, padding: '20px 16px',
            display: 'flex', alignItems: 'center', gap: 16,
            cursor: 'pointer',
            boxShadow: '0 4px 20px rgba(95,186,71,.08)',
          }}
          onClick={() => setView('smm_list')}
        >
          <div className="cat-icon" style={{ background: 'linear-gradient(135deg, #5FBA47, #3a8a28)', color: '#fff', fontSize: 30 }}>👥</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_boost}</div>
            <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{T.tg_boost_desc}</div>
          </div>
          <div style={{ color: '#5FBA47', fontSize: 24, fontWeight: 300 }}>›</div>
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
                    {cat.discount_stars && (
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#ff6b2b', marginTop: 4 }}>
                        🎉 Скидка в честь открытия магазина
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="price-pill" style={{ flex: 1, justifyContent: 'center', fontSize: 15, padding: '9px 12px' }}>
                    {cat.discount_stars ? (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ textDecoration: 'line-through', color: 'var(--muted)', fontSize: 13 }}>⭐{cat.price_stars}</span>
                        <span style={{ fontWeight: 800, color: '#ff6b2b' }}>⭐{cat.discount_stars}</span>
                      </span>
                    ) : localPrice(cat.price_stars, cat.price_usd)}
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

  // ─── SMM список послуг → одразу на форму ──────────────────────────────────
  if (view === 'smm_list') {
    if (smmServices.length === 0) return (
      <div className="page">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
          <button onClick={() => setView('menu')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--orange)', fontSize: 26, lineHeight: 1 }}>‹</button>
          <h1 style={{ margin: 0 }}>{T.tg_boost}</h1>
        </div>
        <div className="card"><div className="skeleton" style={{ height: 80 }} /></div>
      </div>
    )
    // single service → go directly to form
    const s = smmServices[0]
    setSmmDone(null); setSmmError(null); setSmmLink(''); setSmmQty(10); setSmmCustom('')
    setView('smm')
    return null
  }

  // ─── SMM замовлення ────────────────────────────────────────────────────────
  if (view === 'smm') {
    const svc = smmServices[0]
    const effectiveQty = Math.max(10, smmQty)
    const priceStars = svc ? Math.max(1, Math.round(effectiveQty / 100 * svc.price_per_100_stars)) : 0
    const balance = me?.balance_stars ?? 0
    const canOrder = smmLink.trim().length > 0 && balance >= priceStars && !smmLoading

    async function orderSmm() {
      if (!svc || !canOrder) return
      setSmmLoading(true); setSmmError(null)
      try {
        const res = await smmApi.order('tg_subscribers', smmLink.trim(), effectiveQty)
        setSmmDone(res)
        onBuy?.()
      } catch (e: any) {
        setSmmError(e.message === 'insufficient_balance'
          ? (lang === 'ru' ? 'Недостаточно звёзд' : 'Недостатньо зірок')
          : (e.message ?? 'Ошибка'))
      } finally { setSmmLoading(false) }
    }

    if (smmDone) return (
      <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '70vh', gap: 0 }}>
        <div style={{
          background: 'linear-gradient(135deg, #0e1a0e 0%, #0a140a 100%)',
          border: '1px solid rgba(95,186,71,.3)',
          borderRadius: 24, padding: '36px 28px', textAlign: 'center', width: '100%', maxWidth: 340,
        }}>
          <div style={{ fontSize: 56, marginBottom: 14 }}>✅</div>
          <div style={{ fontWeight: 800, fontSize: 22, marginBottom: 8 }}>
            {lang === 'ru' ? 'Заказ принят!' : 'Замовлення прийнято!'}
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 20 }}>
            #{smmDone.order_id} · ⭐{smmDone.stars_spent}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.55, marginBottom: 24 }}>
            {lang === 'ru'
              ? '🚀 Подписчики начнут поступать в течение 0–10 минут'
              : '🚀 Підписники почнуть надходити протягом 0–10 хвилин'}
          </div>
          <button className="btn btn-secondary" style={{ width: '100%' }} onClick={() => { setSmmDone(null); setSmmQty(10); setSmmCustom(''); setSmmLink('') }}>
            {lang === 'ru' ? '+ Ещё заказ' : '+ Ще замовлення'}
          </button>
        </div>
      </div>
    )

    const infoItems = [
      { icon: '🔗', text: lang === 'ru' ? 'Работает только с каналами (https://t.me/...)' : 'Працює лише з каналами (https://t.me/...)' },
      { icon: '🚀', text: lang === 'ru' ? 'Старт: 0–10 минут' : 'Старт: 0–10 хвилин' },
      { icon: '⛔️', text: lang === 'ru' ? 'Списания: 0–2%. При массовом бане от Telegram — шанс нулевой.' : 'Списання: 0–2%. При масовому бані від Telegram — шанс нульовий.' },
      { icon: '♻️', text: lang === 'ru' ? 'Гарантия 365 дней — восстановим, если спишутся.' : 'Гарантія 365 днів — відновимо, якщо спишуться.' },
    ]

    const PRESETS = [10, 50, 100, 500, 1000]

    return (
      <div className="page">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
          <button onClick={() => setView('menu')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--orange)', fontSize: 26, lineHeight: 1 }}>‹</button>
          <div>
            <div style={{ fontWeight: 800, fontSize: 19 }}>👥 {lang === 'ru' ? 'Накрутка подписчиков' : 'Накрутка підписників'}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>Telegram</div>
          </div>
        </div>

        {/* Service hero card */}
        {svc && (
          <div style={{
            background: 'linear-gradient(135deg, #0e1a0e 0%, #0d180d 100%)',
            border: '1px solid rgba(95,186,71,.3)',
            borderRadius: 18, padding: '16px 18px', marginBottom: 14,
            display: 'flex', alignItems: 'center', gap: 16,
          }}>
            <div style={{
              width: 52, height: 52, borderRadius: 16, flexShrink: 0,
              background: 'linear-gradient(135deg, #5FBA47, #3a8a28)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26,
            }}>👥</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 16 }}>{svc.title}</div>
              <div style={{ fontSize: 12, color: '#4cff8f', marginTop: 3 }}>✅ {lang === 'ru' ? 'Гарантия 365 дней' : 'Гарантія 365 днів'}</div>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontWeight: 800, fontSize: 20, color: 'var(--orange)', lineHeight: 1 }}>⭐{svc.price_per_100_stars}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{lang === 'ru' ? 'за 100 шт' : 'за 100 шт'}</div>
            </div>
          </div>
        )}

        {/* Info */}
        <div style={{
          background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.08)',
          borderRadius: 14, padding: '12px 14px', marginBottom: 16,
        }}>
          {infoItems.map((item, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: i < infoItems.length - 1 ? 9 : 0 }}>
              <span style={{ fontSize: 15, flexShrink: 0, lineHeight: 1.4 }}>{item.icon}</span>
              <span style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.45 }}>{item.text}</span>
            </div>
          ))}
        </div>

        {/* Form */}
        <div style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 18, padding: '18px 16px',
        }}>
          {/* Link */}
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', marginBottom: 8, letterSpacing: .4 }}>
              {lang === 'ru' ? 'ССЫЛКА НА КАНАЛ' : 'ПОСИЛАННЯ НА КАНАЛ'}
            </div>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 16, pointerEvents: 'none' }}>🔗</span>
              <input
                type="text"
                placeholder="https://t.me/yourchannel"
                value={smmLink}
                onChange={e => setSmmLink(e.target.value)}
                style={{
                  width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
                  borderRadius: 12, padding: '12px 14px 12px 38px',
                  color: 'var(--text)', fontSize: 14, boxSizing: 'border-box',
                }}
              />
            </div>
          </div>

          {/* Quantity */}
          <div style={{ marginBottom: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', letterSpacing: .4 }}>
                {lang === 'ru' ? 'КОЛИЧЕСТВО' : 'КІЛЬКІСТЬ'}
              </div>
              <div style={{ fontWeight: 800, fontSize: 15, color: 'var(--text)' }}>
                {effectiveQty} <span style={{ fontWeight: 400, fontSize: 12, color: 'var(--muted)' }}>{lang === 'ru' ? 'подп.' : 'підп.'}</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginBottom: 10 }}>
              {PRESETS.map(q => {
                const active = effectiveQty === q && !smmCustom
                return (
                  <button key={q} onClick={() => { setSmmQty(q); setSmmCustom('') }} style={{
                    flex: 1, minWidth: 46, padding: '9px 4px', borderRadius: 10, fontSize: 13,
                    fontWeight: 700, cursor: 'pointer', transition: 'all .15s',
                    background: active ? 'linear-gradient(135deg, #5FBA47, #3a8a28)' : 'var(--card2)',
                    color: active ? '#fff' : 'var(--text)',
                    border: '1px solid ' + (active ? '#5FBA47' : 'var(--border)'),
                    boxShadow: active ? '0 2px 10px rgba(95,186,71,.3)' : 'none',
                  }}>{q}</button>
                )
              })}
            </div>
            <input
              type="number" min={10} max={10000}
              value={smmCustom}
              onChange={e => {
                setSmmCustom(e.target.value)
                const v = Math.max(10, Math.min(10000, parseInt(e.target.value) || 10))
                setSmmQty(v)
              }}
              style={{
                width: '100%', background: 'var(--card2)', border: '1px solid ' + (smmCustom ? 'rgba(95,186,71,.5)' : 'var(--border)'),
                borderRadius: 12, padding: '11px 14px', color: 'var(--text)', fontSize: 14, boxSizing: 'border-box',
              }}
              placeholder={lang === 'ru' ? 'Или введите своё число (10–10 000)' : 'Або введіть своє число (10–10 000)'}
            />
          </div>

          {/* Total */}
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            background: 'linear-gradient(135deg, rgba(95,186,71,.1), rgba(95,186,71,.05))',
            border: '1px solid rgba(95,186,71,.2)',
            borderRadius: 14, padding: '14px 16px', marginBottom: 14,
          }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 2 }}>{lang === 'ru' ? 'К оплате' : 'До сплати'}</div>
              <div style={{ fontSize: 13, color: 'var(--text2)' }}>
                {effectiveQty} {lang === 'ru' ? 'подписчиков' : 'підписників'} × ⭐{svc?.price_per_100_stars}/100
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 800, fontSize: 28, color: '#5FBA47', lineHeight: 1 }}>⭐{priceStars}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                {lang === 'ru' ? 'Баланс:' : 'Баланс:'} ⭐{balance}
              </div>
            </div>
          </div>

          {smmError && (
            <div style={{
              background: 'rgba(255,68,68,.08)', border: '1px solid rgba(255,68,68,.25)',
              borderRadius: 10, padding: '10px 12px', fontSize: 13, color: '#ff6666', marginBottom: 12,
            }}>❌ {smmError}</div>
          )}

          <button
            className="btn btn-primary"
            style={{
              width: '100%', fontSize: 16, fontWeight: 800, padding: '14px',
              background: canOrder ? 'linear-gradient(135deg, #5FBA47, #3a8a28)' : undefined,
              boxShadow: canOrder ? '0 4px 20px rgba(95,186,71,.3)' : 'none',
            }}
            disabled={!canOrder}
            onClick={orderSmm}
          >
            {smmLoading ? '⏳ ...' : canOrder ? `${lang === 'ru' ? 'Заказать' : 'Замовити'} — ⭐${priceStars}` : lang === 'ru' ? 'Введите ссылку на канал' : 'Введіть посилання на канал'}
          </button>
        </div>
      </div>
    )
  }

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
