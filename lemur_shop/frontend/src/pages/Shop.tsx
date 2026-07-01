import { useState, useEffect, useRef } from 'react'
import { api, smmApi, fortuneApi, type Category, type BuyResult, type Me, type SmmService, type NftItem, type FortuneSpinResult } from '../api'
import { getT, type Lang } from '../i18n'
import LegalFooter from '../components/LegalFooter'
import BioPromoButton from '../components/BioPromoButton'

interface Props { lang: Lang; me: Me | null; onGoToBalance: () => void; onGoToProfile?: () => void; onBuy?: () => void }

type View = 'menu' | 'list' | 'buying' | 'success' | 'error' | 'stars' | 'smm' | 'smm_list' | 'smm_reactions' | 'nft'

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

const EYE_ICON = (
  <svg viewBox="0 0 24 24" fill="currentColor" width="26" height="26">
    <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
  </svg>
)

type CatDef = { cat: string; label: string; emoji: string; color: string; bg: string; prob: number }

const FORTUNE_CATS_DATA: CatDef[] = [
  { cat: 'mm', label: '🇲🇲 Мьянма',    emoji: '🎁', color: '#22c55e', bg: 'rgba(34,197,94,.15)',  prob: 25 },
  { cat: 'us', label: '🇺🇸 США',        emoji: '🎁', color: '#3b82f6', bg: 'rgba(59,130,246,.15)', prob: 25 },
  { cat: 'co', label: '🇨🇴 Колумбия',  emoji: '💫', color: '#8b5cf6', bg: 'rgba(139,92,246,.15)', prob: 20 },
  { cat: 'de', label: '🇩🇪 Германия',  emoji: '💎', color: '#f59e0b', bg: 'rgba(245,158,11,.15)', prob: 15 },
  { cat: 'ua', label: '🇺🇦 Украина',   emoji: '🏆', color: '#ef4444', bg: 'rgba(239,68,68,.15)',  prob: 10 },
  { cat: 'kz', label: '🇰🇿 Казахстан', emoji: '🔥', color: '#ec4899', bg: 'rgba(236,72,153,.15)', prob: 5  },
]

const ITEM_W = 126
const ITEM_GAP = 6
const ITEM_STRIDE = ITEM_W + ITEM_GAP
const WIN_IDX = 48
const REEL_LEN = 60

function buildReel(winCat: string): CatDef[] {
  const total = FORTUNE_CATS_DATA.reduce((s, c) => s + c.prob, 0)
  const items: CatDef[] = []
  for (let i = 0; i < REEL_LEN; i++) {
    let r = Math.floor(Math.random() * total)
    let picked = FORTUNE_CATS_DATA[0]
    for (const c of FORTUNE_CATS_DATA) { r -= c.prob; if (r < 0) { picked = c; break } }
    items.push(picked)
  }
  items[WIN_IDX] = FORTUNE_CATS_DATA.find(c => c.cat === winCat) ?? FORTUNE_CATS_DATA[0]
  return items
}

function ReelItem({ cat }: { cat: CatDef }) {
  return (
    <div style={{
      minWidth: ITEM_W, height: 94, borderRadius: 12, flexShrink: 0,
      background: cat.bg, border: `1.5px solid ${cat.color}44`,
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 5,
    }}>
      <div style={{ fontSize: 28 }}>{cat.emoji}</div>
      <div style={{ fontSize: 9, fontWeight: 700, color: cat.color, textAlign: 'center', lineHeight: 1.3, padding: '0 6px' }}>
        {cat.label.split(' ').slice(1).join(' ')}
      </div>
    </div>
  )
}

function RandomAccountButton({ me, onBuy }: { me: Me | null; onBuy?: () => void }) {
  const [phase, setPhase] = useState<'idle' | 'spinning' | 'done'>('idle')
  const [reel, setReel] = useState<CatDef[]>(() =>
    Array.from({ length: REEL_LEN }, (_, i) => FORTUNE_CATS_DATA[i % FORTUNE_CATS_DATA.length])
  )
  const [result, setResult] = useState<FortuneSpinResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const trackRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  if (!me?.is_admin) return null

  async function spin() {
    if (phase === 'spinning') return
    setErr(null)
    setResult(null)
    setPhase('spinning')
    if (trackRef.current) {
      trackRef.current.style.transition = 'none'
      trackRef.current.style.transform = 'translateX(0)'
    }
    try {
      const r = await fortuneApi.spin()
      const winCat = r.won && r.prize_cat
        ? r.prize_cat
        : FORTUNE_CATS_DATA[Math.floor(Math.random() * FORTUNE_CATS_DATA.length)].cat
      const newReel = buildReel(winCat)
      setReel(newReel)
      setTimeout(() => {
        if (trackRef.current && containerRef.current) {
          const cw = containerRef.current.offsetWidth
          const targetX = -(WIN_IDX * ITEM_STRIDE) + cw / 2 - ITEM_W / 2
          trackRef.current.style.transition = 'transform 5.5s cubic-bezier(0.08, 0.82, 0.17, 1)'
          trackRef.current.style.transform = `translateX(${targetX}px)`
        }
        setTimeout(() => {
          setResult(r)
          setPhase('done')
          onBuy?.()
        }, 5700)
      }, 60)
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Ошибка. Попробуйте позже.')
      setPhase('idle')
    }
  }

  function reset() {
    setPhase('idle')
    setResult(null)
    setErr(null)
    if (trackRef.current) {
      trackRef.current.style.transition = 'none'
      trackRef.current.style.transform = 'translateX(0)'
    }
    setReel(Array.from({ length: REEL_LEN }, (_, i) => FORTUNE_CATS_DATA[i % FORTUNE_CATS_DATA.length]))
  }

  return (
    <div style={{
      background: 'linear-gradient(135deg, #2A1A3D 0%, #1A0F2E 50%, #0D0618 100%)',
      border: '1px solid rgba(255,200,80,.35)',
      borderRadius: 20, padding: '14px 14px 16px', marginBottom: 14,
      boxShadow: '0 8px 32px rgba(255,180,40,.15), inset 0 1px 0 rgba(255,255,255,.05)',
    }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div style={{
          width: 42, height: 42, borderRadius: 13, flexShrink: 0,
          background: 'linear-gradient(135deg, #FFD166, #FF8C42)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
          boxShadow: '0 4px 12px rgba(255,180,40,.45)',
        }}>🎲</div>
        <div>
          <div style={{ fontWeight: 800, fontSize: 15, color: '#FFD166' }}>Случайный TG аккаунт</div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>Стоимость прокрутки: ⭐100</div>
        </div>
      </div>

      {/* Probability badges */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 12 }}>
        {FORTUNE_CATS_DATA.map(c => (
          <div key={c.cat} style={{
            background: c.bg, border: `1px solid ${c.color}55`,
            borderRadius: 8, padding: '3px 8px',
            fontSize: 10, fontWeight: 700, color: c.color,
            display: 'flex', alignItems: 'center', gap: 3,
          }}>
            {c.emoji} {c.label.split(' ').slice(1).join(' ')}
            <span style={{ opacity: .65, fontWeight: 400 }}>{c.prob}%</span>
          </div>
        ))}
      </div>

      {/* Reel */}
      <div ref={containerRef} style={{
        position: 'relative', overflow: 'hidden', height: 112,
        borderRadius: 14, marginBottom: 12,
        background: 'rgba(0,0,0,.5)',
        border: '1px solid rgba(255,200,80,.15)',
      }}>
        {/* Fade left */}
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: 56, zIndex: 3, pointerEvents: 'none',
          background: 'linear-gradient(90deg, rgba(0,0,0,.65) 0%, transparent 100%)',
        }} />
        {/* Fade right */}
        <div style={{
          position: 'absolute', right: 0, top: 0, bottom: 0, width: 56, zIndex: 3, pointerEvents: 'none',
          background: 'linear-gradient(270deg, rgba(0,0,0,.65) 0%, transparent 100%)',
        }} />
        {/* Center selector box */}
        <div style={{
          position: 'absolute', left: '50%', top: 0, bottom: 0, zIndex: 2, pointerEvents: 'none',
          transform: 'translateX(-50%)', width: ITEM_W + 6,
          border: '2px solid rgba(255,200,80,.8)', borderRadius: 14,
          boxShadow: '0 0 28px rgba(255,180,40,.4), inset 0 0 14px rgba(255,180,40,.08)',
        }} />
        {/* Top arrow */}
        <div style={{
          position: 'absolute', left: '50%', top: 1, transform: 'translateX(-50%)',
          color: '#FFD166', fontSize: 13, zIndex: 4, lineHeight: 1,
        }}>▼</div>
        {/* Bottom arrow */}
        <div style={{
          position: 'absolute', left: '50%', bottom: 1, transform: 'translateX(-50%)',
          color: '#FFD166', fontSize: 13, zIndex: 4, lineHeight: 1,
        }}>▲</div>

        {/* Scrolling track */}
        <div ref={trackRef} style={{
          display: 'flex', gap: ITEM_GAP, alignItems: 'center',
          paddingLeft: ITEM_GAP, height: '100%', willChange: 'transform',
        }}>
          {reel.map((c, i) => <ReelItem key={i} cat={c} />)}
        </div>
      </div>

      {/* Actions */}
      {phase === 'idle' && (
        <button onClick={spin} style={{
          width: '100%', padding: '13px', fontSize: 15, fontWeight: 800,
          background: 'linear-gradient(135deg, #FFD166, #FF8C42)',
          color: '#1A0F2E', border: 'none', borderRadius: 14, cursor: 'pointer',
          boxShadow: '0 4px 18px rgba(255,180,40,.45)',
        }}>
          🎲 Открыть кейс
        </button>
      )}

      {phase === 'spinning' && (
        <button disabled style={{
          width: '100%', padding: '13px', fontSize: 14, fontWeight: 700,
          background: 'rgba(255,180,40,.1)', color: 'rgba(255,209,102,.6)',
          border: '1px solid rgba(255,180,40,.25)', borderRadius: 14, cursor: 'not-allowed',
        }}>
          🎰 Крутим...
        </button>
      )}

      {phase === 'done' && result && (
        <div>
          <div style={{
            padding: '12px 14px', borderRadius: 14, marginBottom: 10,
            background: result.won ? 'rgba(74,222,128,.1)' : 'rgba(255,255,255,.04)',
            border: result.won ? '1px solid rgba(74,222,128,.35)' : '1px solid rgba(255,255,255,.1)',
          }}>
            {result.won ? (
              <>
                <div style={{ fontWeight: 800, color: '#4ade80', fontSize: 14, marginBottom: 4 }}>
                  🎉 Выигрыш! {result.prize_emoji} {result.prize_label}
                </div>
                {result.phone && <div style={{ color: 'var(--text2)', fontSize: 13 }}>Номер: <b>{result.phone}</b></div>}
                <div style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4 }}>Аккаунт уже в разделе «Заказы»</div>
              </>
            ) : (
              <div style={{ color: 'var(--text2)', fontSize: 13 }}>
                Не повезло. Пул пополнен: <b>{result.pool_balance}⭐</b> / {result.pool_threshold}⭐
              </div>
            )}
          </div>
          <button onClick={reset} style={{
            width: '100%', padding: '11px', fontSize: 13, fontWeight: 700,
            background: 'rgba(255,180,40,.1)', color: '#FFD166',
            border: '1px solid rgba(255,180,40,.3)', borderRadius: 14, cursor: 'pointer',
          }}>
            Крутить ещё раз
          </button>
        </div>
      )}

      {err && <div style={{ color: '#ef4444', fontSize: 12, marginTop: 8, fontWeight: 600 }}>⚠️ {err}</div>}
    </div>
  )
}

interface ConfirmProps {
  cat: Category; me: Me | null; lang: Lang
  onConfirm(): void; onCancel(): void
}

function ConfirmModal({ cat, me, lang, onConfirm, onCancel }: ConfirmProps) {
  const T = getT(lang)
  const clicked = useRef(false)
  function handleConfirm() {
    if (clicked.current) return
    clicked.current = true
    onConfirm()
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

        <div style={{
          background: 'rgba(0,0,0,.25)', borderRadius: 14,
          border: '1px solid var(--border)', padding: '14px 16px', marginBottom: 20,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontWeight: 700, fontSize: 15 }}>{T.final_price}</span>
          {cat.discount_stars ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ textDecoration: 'line-through', color: 'var(--muted)', fontSize: 16 }}>⭐{cat.price_stars}</span>
              <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                <span style={{ fontWeight: 800, fontSize: 24, color: '#ff6b2b', lineHeight: 1 }}>⭐{cat.discount_stars}</span>
                <span style={{ fontWeight: 400, fontSize: 12, color: 'var(--muted)' }}>(${(cat.discount_stars * 0.013).toFixed(2)})</span>
              </span>
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
          <button className="btn btn-primary" style={{ flex: 2 }} onClick={handleConfirm}>{T.confirm}</button>
        </div>
      </div>
    </div>
  )
}

export default function Shop({ lang, me, onGoToBalance, onGoToProfile, onBuy }: Props) {
  const T = getT(lang)
  const [view, setView]       = useState<View>('menu')
  const [cats, setCats]       = useState<Category[]>([])
  const [result, setResult]   = useState<BuyResult | null>(null)
  const [errMsg, setErr]      = useState('')
  const [code, setCode]       = useState('')
  const [gettingCode, setGettingCode] = useState(false)
  const [copied, setCopied]   = useState<'phone' | 'code' | ''>('')
  const [confirmCat, setConfirmCat] = useState<Category | null>(null)
  const buyingRef = useRef(false)
  const [smmServices, setSmmServices] = useState<SmmService[]>([])
  const [selectedSmmKey, setSelectedSmmKey] = useState('tg_subscribers')
  const [smmLink, setSmmLink] = useState('')
  const [smmQty, setSmmQty] = useState(100)
  const [smmCustom, setSmmCustom] = useState('')
  const [smmLoading, setSmmLoading] = useState(false)
  const [smmError, setSmmError] = useState<string | null>(null)
  const [smmDone, setSmmDone] = useState<{ order_id: number; stars_spent: number } | null>(null)

  // NFT state
  const [nftItems, setNftItems] = useState<NftItem[]>([])
  const [nftLoading, setNftLoading] = useState(false)
  const [nftSearch, setNftSearch] = useState('')
  const [nftSearchInput, setNftSearchInput] = useState('')
  const [nftConfirm, setNftConfirm] = useState<NftItem | null>(null)
  const [nftBuying, setNftBuying] = useState(false)
  const [nftDone, setNftDone] = useState<{ order_id: number; stars_spent: number; expires_at: string; username: string; duration_days: number } | null>(null)
  const nftSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    api.categories().catch(() => []).then(setCats)
    smmApi.services().then(setSmmServices).catch(() => {})
  }, [])

  useEffect(() => {
    if (view !== 'nft') return
    setNftLoading(true)
    api.nftList(nftSearch || undefined).then(setNftItems).catch(() => setNftItems([])).finally(() => setNftLoading(false))
  }, [view, nftSearch])

  function handleNftSearchInput(val: string) {
    setNftSearchInput(val)
    if (nftSearchTimer.current) clearTimeout(nftSearchTimer.current)
    nftSearchTimer.current = setTimeout(() => setNftSearch(val), 400)
  }

  async function buyNft(nft: NftItem) {
    if (nftBuying) return
    setNftBuying(true)
    try {
      const res = await api.nftBuy(nft.id)
      setNftDone({ order_id: res.order_id, stars_spent: res.stars_spent, expires_at: res.expires_at, username: nft.username, duration_days: nft.duration_days })
      setNftConfirm(null)
      onBuy?.()
    } catch (e: any) {
      alert(e.message ?? 'Помилка')
    } finally {
      setNftBuying(false)
    }
  }

  async function buy(cat: Category) {
    if (buyingRef.current) return
    buyingRef.current = true
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
      const errMap: Record<string, keyof typeof T> = {
        no_accounts:     'err_no_accounts',
        service_unavailable: 'err_service_unavail',
        timeout:         'err_timeout',
        buy_failed:      'err_buy_failed',
        duplicate_order: 'err_duplicate_order',
      }
      const key = errMap[e.message]
      setErr(key ? String(T[key]) : T.buy_error)
      setView('error')
    } finally {
      buyingRef.current = false
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
        {/* Hero balance card */}
        <div style={{
          background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
          border: '1px solid rgba(244,169,0,.22)',
          borderRadius: 20, padding: '20px 18px', marginBottom: 18,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: -30, right: -30, width: 150, height: 150, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(244,169,0,.12) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />
          <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: 1, marginBottom: 4 }}>
            {T.balance.toUpperCase()}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1 }}>
              <span style={{ fontWeight: 800, fontSize: 30 }}>⭐{starsBalance}</span>
              <span style={{ fontWeight: 400, fontSize: 13, marginLeft: 7, color: 'var(--muted)' }}>(${usdDisplay})</span>
            </div>
            <BioPromoButton lang={lang} />
          </div>
        </div>

        <h1 style={{ marginBottom: 14, fontSize: 19 }}>{T.shop}</h1>

        {/* TG Accounts card */}
        <div style={{
          background: 'linear-gradient(135deg, #0d1520 0%, #111a2e 100%)',
          border: '1px solid rgba(42,171,238,.25)',
          borderRadius: 20, padding: '18px 16px', marginBottom: 10,
          boxShadow: '0 6px 28px rgba(42,171,238,.1)',
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: -20, right: -20, width: 120, height: 120,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(42,171,238,.1) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 16, flexShrink: 0,
              background: 'linear-gradient(135deg, #2AABEE, #1178B8)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(42,171,238,.35)',
              color: '#fff',
            }}>{TG_ICON}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_accounts}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>{T.tg_accounts_desc}</div>
            </div>
          </div>
          <button className="btn" onClick={() => setView('list')} style={{
            width: '100%', padding: '11px',
            background: 'linear-gradient(135deg, #2AABEE, #1178B8)',
            color: '#fff', fontSize: 14, fontWeight: 700,
            boxShadow: '0 3px 14px rgba(42,171,238,.35)',
          }}>
            {T.buy} →
          </button>
        </div>

        {/* SMM Boost card */}
        <div className="smm-card" style={{
          borderRadius: 20, padding: '18px 16px',
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 16, flexShrink: 0,
              background: 'linear-gradient(135deg, #5FBA47, #2d7a1c)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26,
              boxShadow: '0 4px 14px rgba(95,186,71,.35)',
            }}>👥</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_boost}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>{T.tg_boost_desc}</div>
            </div>
          </div>
          <button className="btn btn-green" onClick={() => setView('smm_list')} style={{
            width: '100%', padding: '11px', fontSize: 14, fontWeight: 700,
          }}>
            {T.boost_order_btn} →
          </button>
        </div>

        {/* NFT Usernames card — hidden until feature is ready */}
        <div style={{ display: 'none' }}><div style={{
          background: 'linear-gradient(135deg, #1a0d2e 0%, #130924 100%)',
          border: '1px solid rgba(160,80,255,.25)',
          borderRadius: 20, padding: '18px 16px', marginTop: 10,
          position: 'relative', overflow: 'hidden',
          boxShadow: '0 6px 28px rgba(140,60,255,.1)',
        }}>
          <div style={{
            position: 'absolute', top: -20, right: -20, width: 120, height: 120, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(160,80,255,.12) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 16, flexShrink: 0,
              background: 'linear-gradient(135deg, #9B59F5, #6A0DAD)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(155,89,245,.4)',
              color: '#fff', fontWeight: 900, fontSize: 28,
            }}>@</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 17 }}>NFT Юзернейми</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>Оренда красивих @username в Telegram</div>
            </div>
          </div>
          <button className="btn" onClick={() => setView('nft')} style={{
            width: '100%', padding: '11px',
            background: 'linear-gradient(135deg, #9B59F5, #6A0DAD)',
            color: '#fff', fontSize: 14, fontWeight: 700,
            boxShadow: '0 3px 14px rgba(155,89,245,.35)',
          }}>
            Орендувати →
          </button>
        </div></div>

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

        <RandomAccountButton me={me} onBuy={onBuy} />

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
            <div className="card"><div className="skeleton" style={{ height: 72 }} /></div>
            <div className="card"><div className="skeleton" style={{ height: 72 }} /></div>
          </>
        ) : (
          <>
            {cats.some(c => c.discount_stars) && (
              <div style={{
                fontSize: 12, fontWeight: 700, color: '#ff6b2b',
                background: 'rgba(255,107,43,.1)', border: '1px solid rgba(255,107,43,.25)',
                borderRadius: 10, padding: '8px 14px', textAlign: 'center', marginBottom: 4,
              }}>
                🎉 Акция открытия магазина — скидки на все аккаунты
              </div>
            )}
            {cats.map(cat => (
              <div key={cat.category} className="card" style={{ padding: '12px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                  <div style={{ fontSize: 36, flexShrink: 0, lineHeight: 1 }}>{cat.flag}</div>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: 16 }}>
                      {lang === 'ru' ? cat.title_ru : lang === 'ua' ? cat.title_ua : cat.title}
                      {cat.phone_prefix && (
                        <span style={{ fontWeight: 400, fontSize: 12, color: 'var(--muted)', marginLeft: 6 }}>
                          ({cat.phone_prefix})
                        </span>
                      )}
                    </div>
                    <div className="muted" style={{ fontSize: 11, marginTop: 1 }}>Telegram account</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div className="price-pill" style={{ flex: 1, justifyContent: 'center', padding: '8px 10px' }}>
                    {cat.discount_stars ? (
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <span style={{ textDecoration: 'line-through', color: 'var(--muted)', fontSize: 12 }}>⭐{cat.price_stars}</span>
                        <span style={{ fontWeight: 800, color: '#ff6b2b', fontSize: 15 }}>⭐{cat.discount_stars}</span>
                        <span style={{ color: 'var(--muted)', fontSize: 11 }}>(${(cat.discount_stars * 0.013).toFixed(2)})</span>
                      </span>
                    ) : localPrice(cat.price_stars, cat.price_usd)}
                  </div>
                  <button
                    className="btn btn-primary"
                    style={{ width: 'auto', padding: '9px 20px', fontSize: 14, flexShrink: 0 }}
                    onClick={() => setConfirmCat(cat)}
                  >{T.buy}</button>
                </div>
              </div>
            ))}
          </>
        )}

      </div>
    </>
  )

  // ─── SMM список послуг ────────────────────────────────────────────────────
  if (view === 'smm_list') return (
    <div className="page">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button onClick={() => setView('menu')} style={{
          width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'var(--card2)', border: '1px solid var(--border)', cursor: 'pointer', fontSize: 20, color: 'var(--text2)', flexShrink: 0,
        }}>‹</button>
        <div>
          <div style={{ fontWeight: 800, fontSize: 20 }}>{T.tg_boost}</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>{T.smm_promo}</div>
        </div>
      </div>

      {smmServices.length === 0 ? (
        <div style={{ borderRadius: 20, height: 120 }} className="skeleton" />
      ) : smmServices.filter(svc => ['tg_subscribers', 'tg_views', 'tg_reactions'].includes(svc.key)).map(svc => {
        const isViews = svc.key === 'tg_views'
        const isReactCard = svc.key === 'tg_reactions'
        const badgeQty = isViews ? 1000 : isReactCard ? 300 : 100
        const badgeStars = Math.round(badgeQty / 100 * svc.price_per_100_stars)
        const badgeWord = isViews ? T.smm_views_word : isReactCard ? T.smm_reactions_word : T.smm_subs_word
        const cardTitle = isViews ? T.smm_views_title : isReactCard ? T.smm_reactions_title : T.smm_subs_title
        const cardSub = isViews
          ? <span style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, display: 'block' }}>
              {lang === 'ru' ? 'Пост канала · до нескольких часов' : lang === 'ua' ? 'Пост каналу · до кількох годин' : 'Channel post · up to a few hours'}
            </span>
          : isReactCard
            ? <span style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3, display: 'block' }}>
                {lang === 'ru' ? 'Почти мгновенная накрутка реакций' : lang === 'ua' ? 'Майже миттєва накрутка реакцій' : 'Almost instant reaction boost'}
              </span>
            : <span style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3, display: 'block' }}>{T.smm_channels_only}</span>
        return (
          <div
            key={svc.key}
            className="smm-card"
            onClick={() => {
              if (isReactCard) {
                setSelectedSmmKey('tg_reactions'); setSmmDone(null); setSmmError(null); setSmmLink(''); setSmmQty(15); setSmmCustom('')
                setView('smm_reactions')
              } else {
                setSelectedSmmKey(svc.key); setSmmDone(null); setSmmError(null); setSmmLink(''); setSmmQty(svc.min); setSmmCustom('')
                setView('smm')
              }
            }}
            style={{ borderRadius: 20, padding: '16px', marginBottom: 10 }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 52, height: 52, borderRadius: 16, flexShrink: 0,
                background: isReactCard ? 'linear-gradient(135deg, #2d2200, #3a2e00)' : 'linear-gradient(135deg, #5FBA47, #2d7a1c)',
                border: isReactCard ? '1px solid rgba(244,169,0,.3)' : 'none',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: isReactCard ? 20 : (isViews ? 0 : 25),
                boxShadow: isReactCard ? '0 4px 14px rgba(244,169,0,.25)' : '0 4px 14px rgba(95,186,71,.4)',
                color: '#fff',
              }}>
                {isReactCard ? '😊' : isViews ? EYE_ICON : '👥'}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 800, fontSize: 15 }}>{cardTitle}</div>
                {!isReactCard && !isViews && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 5, fontWeight: 700, fontSize: 12, color: '#7FD465' }}>
                    <span style={{ fontSize: 14 }}>♻️</span>
                    <span>{T.smm_guarantee}</span>
                  </div>
                )}
                {cardSub}
              </div>

              {/* Right price badge */}
              <div style={{
                flexShrink: 0,
                background: 'linear-gradient(160deg, #F0A800, #C87800)',
                borderRadius: 16, padding: '13px 15px',
                textAlign: 'center',
                boxShadow: '0 0 22px rgba(255,180,0,.75), 0 4px 16px rgba(200,120,0,.55)',
              }}>
                <div style={{ fontWeight: 900, fontSize: 18, color: '#fff', lineHeight: 1, textShadow: '0 0 10px rgba(255,255,255,.5)' }}>{badgeQty}</div>
                <div style={{ fontWeight: 700, fontSize: 11, color: 'rgba(255,255,255,.85)', whiteSpace: 'nowrap', marginTop: 2 }}>{badgeWord}</div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,.45)', margin: '4px 0' }}>——</div>
                <div style={{ fontWeight: 900, fontSize: 22, color: '#fff', lineHeight: 1, textShadow: '0 0 12px rgba(255,255,255,.5)' }}>⭐{badgeStars}</div>
              </div>

              <div style={{ color: '#5FBA47', fontSize: 18, fontWeight: 300, flexShrink: 0 }}>›</div>
            </div>
          </div>
        )
      })}
    </div>
  )

  // ─── Накрутка реакцій ──────────────────────────────────────────────────────
  if (view === 'smm_reactions') {
    const INDIVIDUAL_BTNS: { key: string; emoji: string }[] = [
      { key: 'tg_react_like',         emoji: '👍' },
      { key: 'tg_react_dislike',      emoji: '👎' },
      { key: 'tg_react_heart',        emoji: '❤️' },
      { key: 'tg_react_fire',         emoji: '🔥' },
      { key: 'tg_react_poop',         emoji: '💩' },
      { key: 'tg_react_clown',        emoji: '🤡' },
      { key: 'tg_react_middlefinger', emoji: '🖕' },
      { key: 'tg_react_vomit',        emoji: '🤮' },
      { key: 'tg_react_angry',        emoji: '😡' },
      { key: 'tg_react_sunglasses',   emoji: '😎' },
    ]
    const PACK_BTNS: { key: string; emoji: string; label: string }[] = [
      { key: 'tg_react_neg_mix1', emoji: '👎😁😢💩', label: 'Негативний пак' },
    ]
    const svc = smmServices.find(s => s.key === selectedSmmKey) ?? smmServices.find(s => s.key === 'tg_react_neg_mix1')
    const effectiveQty = Math.max(svc?.min ?? 15, smmQty)
    const priceStars = svc ? Math.max(1, Math.round(effectiveQty / 100 * svc.price_per_100_stars)) : 0
    const balance = me?.balance_stars ?? 0
    const canOrder = smmLink.trim().length > 0 && balance >= priceStars && !smmLoading
    const REACT_PRESETS = [15, 50, 100, 500, 1000]

    async function orderReactions() {
      if (!svc || !canOrder) return
      setSmmLoading(true); setSmmError(null)
      try {
        const res = await smmApi.order(svc.key, smmLink.trim(), effectiveQty)
        setSmmDone(res)
        onBuy?.()
      } catch (e: any) {
        const msg: string = e.message ?? ''
        const errMap: Record<string, Record<string, string>> = {
          insufficient_balance: { ru: 'Недостаточно звёзд', ua: 'Недостатньо зірок', en: 'Insufficient stars' },
          insufficient_funds:   { ru: 'Сервис временно недоступен — попробуйте позже', ua: 'Сервіс тимчасово недоступний — спробуйте пізніше', en: 'Service temporarily unavailable — try again later' },
          blocked_channel:      { ru: T.smm_blocked_channel, ua: T.smm_blocked_channel, en: T.smm_blocked_channel },
          user_inactive:        { ru: 'Пост не найден или канал недоступен', ua: 'Пост не знайдено або канал недоступний', en: 'Post not found or channel unavailable' },
          invalid_link:         { ru: 'Неверная ссылка', ua: 'Неправильне посилання', en: 'Invalid link' },
        }
        const k = Object.keys(errMap).find(k => msg.toLowerCase().includes(k.toLowerCase()))
        const friendly = k ? (errMap[k][lang] ?? errMap[k]['ru']) : (lang === 'ru' ? 'Ошибка сервиса — попробуйте позже' : lang === 'ua' ? 'Помилка сервісу — спробуйте пізніше' : 'Service error — try again later')
        if (msg === 'insufficient_balance') {
          setSmmError(lang === 'ru' ? 'Недостаточно звёзд — пополните баланс' : lang === 'ua' ? 'Недостатньо зірок — поповніть баланс' : 'Not enough stars — please top up')
        } else {
          setSmmError(friendly)
        }
      } finally { setSmmLoading(false) }
    }

    if (smmDone) return (
      <div className="page">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <button onClick={() => { setSmmDone(null); setView('smm_list') }} style={{
            width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--card2)', border: '1px solid var(--border)', cursor: 'pointer', fontSize: 20, color: 'var(--text2)', flexShrink: 0,
          }}>‹</button>
          <div style={{ fontWeight: 800, fontSize: 19 }}>{T.smm_accepted}</div>
        </div>
        <div className="smm-card" style={{ borderRadius: 24, padding: '40px 28px', textAlign: 'center', width: '100%' }}>
          <div style={{ fontSize: 60, marginBottom: 16, filter: 'drop-shadow(0 0 20px rgba(95,186,71,.5))' }}>✅</div>
          <div style={{ fontWeight: 800, fontSize: 22, marginBottom: 6 }}>{T.smm_accepted}</div>
          <div style={{
            display: 'inline-flex', gap: 10, alignItems: 'center',
            background: 'rgba(95,186,71,.12)', borderRadius: 20, padding: '5px 14px',
            fontSize: 13, color: '#7FD465', marginBottom: 18,
          }}>
            <span>#{smmDone.order_id}</span><span>·</span><span>⭐{smmDone.stars_spent}</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.6, marginBottom: 24 }}>{T.smm_start_soon}</div>
          <button className="btn btn-secondary" style={{ width: '100%' }}
            onClick={() => { setSmmDone(null); setSmmQty(15); setSmmCustom(''); setSmmLink('') }}>
            {T.smm_new_order}
          </button>
        </div>
      </div>
    )

    return (
      <div className="page">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
          <button onClick={() => setView('smm_list')} style={{
            width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--card2)', border: '1px solid var(--border)', cursor: 'pointer', fontSize: 20, color: 'var(--text2)', flexShrink: 0,
          }}>‹</button>
          <div>
            <div style={{ fontWeight: 800, fontSize: 19 }}>{T.smm_reactions_title}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>Telegram</div>
          </div>
        </div>

        {/* Reaction picker */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8, marginBottom: 10 }}>
            {T.smm_pick_reaction.toUpperCase()}
          </div>
          {/* Individual reactions — 4 per row */}
          {Array.from({ length: Math.ceil(INDIVIDUAL_BTNS.length / 4) }, (_, i) => INDIVIDUAL_BTNS.slice(i * 4, i * 4 + 4)).map((row, ri) => (
            <div key={ri} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
              {row.map(btn => {
                const active = selectedSmmKey === btn.key
                return (
                  <button key={btn.key} onClick={() => { setSelectedSmmKey(btn.key); setSmmQty(15); setSmmCustom('') }}
                    style={{
                      flex: 1, padding: '12px 4px', borderRadius: 14, cursor: 'pointer',
                      border: active ? '2px solid rgba(244,169,0,.7)' : '2px solid var(--border)',
                      background: active ? 'linear-gradient(135deg, rgba(244,169,0,.15), rgba(200,120,0,.08))' : 'var(--card2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      transition: 'all .15s',
                      boxShadow: active ? '0 0 16px rgba(244,169,0,.2)' : 'none',
                    }}>
                    <span style={{ fontSize: 22 }}>{btn.emoji}</span>
                  </button>
                )
              })}
            </div>
          ))}
          {/* Packs — 2 per row, visually distinct */}
          <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
            {PACK_BTNS.map(btn => {
              const active = selectedSmmKey === btn.key
              return (
                <button key={btn.key} onClick={() => { setSelectedSmmKey(btn.key); setSmmQty(15); setSmmCustom('') }}
                  style={{
                    flex: 1, padding: '10px 10px', borderRadius: 14, cursor: 'pointer',
                    border: active ? '2px solid rgba(244,169,0,.8)' : '2px solid rgba(255,255,255,.12)',
                    background: active
                      ? 'linear-gradient(135deg, rgba(244,169,0,.18), rgba(200,120,0,.10))'
                      : 'linear-gradient(135deg, rgba(255,255,255,.06), rgba(255,255,255,.02))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                    transition: 'all .15s',
                    boxShadow: active ? '0 0 18px rgba(244,169,0,.25)' : '0 0 0 rgba(0,0,0,0)',
                  }}>
                  <span style={{ fontSize: 18, letterSpacing: 1 }}>{btn.emoji}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Form card */}
        <div style={{ background: 'var(--card)', border: '1px solid rgba(244,169,0,.22)', borderRadius: 20, padding: '18px 16px', boxShadow: '0 0 28px rgba(244,169,0,.06)' }}>

          {/* Post link input */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8, marginBottom: 8 }}>
              {T.smm_link_post_label.toUpperCase()}
            </div>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: 13, top: '50%', transform: 'translateY(-50%)', fontSize: 16, pointerEvents: 'none', lineHeight: 1 }}>🔗</span>
              <input
                type="text"
                placeholder={T.smm_link_post_ph}
                value={smmLink}
                onChange={e => setSmmLink(e.target.value)}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'var(--card2)',
                  border: '1.5px solid ' + (smmLink ? 'rgba(95,186,71,.45)' : 'var(--border)'),
                  borderRadius: 14, padding: '13px 14px 13px 40px',
                  color: 'var(--text)', fontSize: 14,
                  transition: 'border-color .2s', outline: 'none',
                }}
              />
            </div>
          </div>

          {/* Quantity */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8 }}>{T.smm_qty_reactions_label.toUpperCase()}</div>
              <div style={{ fontWeight: 800, fontSize: 14, color: 'var(--text)' }}>
                {effectiveQty} <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--muted)' }}>{T.smm_reactions_word}</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 7, marginBottom: 10 }}>
              {REACT_PRESETS.map(q => (
                <button key={q}
                  className={'qty-pill' + (effectiveQty === q && !smmCustom ? ' active' : '')}
                  onClick={() => { setSmmQty(q); setSmmCustom('') }}
                >{q >= 1000 ? `${q/1000}K` : q}</button>
              ))}
            </div>
            <input
              type="number" min={svc?.min ?? 15} max={svc?.max ?? 5000}
              value={smmCustom}
              onChange={e => {
                setSmmCustom(e.target.value)
                const min = svc?.min ?? 15; const max = svc?.max ?? 5000
                setSmmQty(Math.max(min, Math.min(max, parseInt(e.target.value) || min)))
              }}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'var(--card2)',
                border: '1.5px solid ' + (smmCustom ? 'rgba(95,186,71,.4)' : 'var(--border)'),
                borderRadius: 12, padding: '11px 14px', color: 'var(--text)', fontSize: 14,
                outline: 'none', transition: 'border-color .2s',
              }}
              placeholder={lang === 'ru' ? 'Или введите своё (15–5000)' : lang === 'ua' ? 'Або введіть своє (15–5000)' : 'Or enter custom (15–5000)'}
            />
          </div>

          {/* Total cost */}
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            background: 'linear-gradient(135deg, rgba(244,169,0,.08) 0%, rgba(200,120,0,.05) 100%)',
            border: '1px solid rgba(244,169,0,.3)',
            borderRadius: 16, padding: '14px 18px', marginBottom: 16,
            boxShadow: '0 2px 16px rgba(244,169,0,.08)',
          }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 3 }}>{T.smm_total_label}</div>
              <div style={{ fontSize: 12, color: 'var(--text2)' }}>
                {effectiveQty} {T.smm_reactions_word}
                <span style={{ color: 'var(--muted)' }}> × ⭐{svc?.price_per_100_stars}/100</span>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="text-orange-grad" style={{ fontWeight: 900, fontSize: 30, lineHeight: 1 }}>⭐{priceStars}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3 }}>{T.smm_balance_label} ⭐{balance}</div>
            </div>
          </div>

          {smmError && (
            <div style={{
              background: 'rgba(255,68,68,.08)', border: '1px solid rgba(255,68,68,.25)',
              borderRadius: 12, padding: '11px 14px', fontSize: 13, color: '#ff7070', marginBottom: 10,
            }}>❌ {smmError}</div>
          )}
          {smmError && balance < priceStars && (
            <button className="btn btn-primary" style={{ width: '100%', marginBottom: 10 }} onClick={onGoToBalance}>
              {lang === 'ru' ? '💰 Пополнить баланс' : lang === 'ua' ? '💰 Поповнити баланс' : '💰 Top up balance'}
            </button>
          )}

          <button
            className={'btn btn-green' + (!canOrder || smmLoading ? ' btn-secondary' : '')}
            style={{ width: '100%', fontSize: 16, padding: '15px' }}
            disabled={!canOrder || smmLoading}
            onClick={orderReactions}
          >
            {smmLoading ? '⏳ ...' : smmLink.trim() ? `${T.smm_order_btn} — ⭐${priceStars}` : T.smm_enter_link}
          </button>
        </div>
      </div>
    )
  }

  // ─── SMM замовлення ────────────────────────────────────────────────────────
  if (view === 'smm') {
    const svc = smmServices.find(s => s.key === selectedSmmKey) ?? smmServices[0]
    const isViews = svc?.key === 'tg_views'
    const isReactions = svc?.key === 'tg_reactions' || svc?.key === 'tg_reactions'
    const effectiveQty = Math.max(svc?.min ?? 10, smmQty)
    const priceStars = svc ? Math.max(1, Math.round(effectiveQty / 100 * svc.price_per_100_stars)) : 0
    const balance = me?.balance_stars ?? 0
    const canOrder = smmLink.trim().length > 0 && balance >= priceStars && !smmLoading

    async function orderSmm() {
      if (!svc || !canOrder) return
      setSmmLoading(true); setSmmError(null)
      try {
        const res = await smmApi.order(svc.key, smmLink.trim(), effectiveQty)
        setSmmDone(res)
        onBuy?.()
      } catch (e: any) {
        const msg: string = e.message ?? ''
        const smmErrMap: Record<string, Record<string, string>> = {
          insufficient_balance:    { ru: 'Недостаточно звёзд', ua: 'Недостатньо зірок', en: 'Insufficient stars' },
          insufficient_funds:      { ru: 'Сервис временно недоступен — попробуйте позже', ua: 'Сервіс тимчасово недоступний — спробуйте пізніше', en: 'Service temporarily unavailable — try again later' },
          blocked_channel:         { ru: T.smm_blocked_channel, ua: T.smm_blocked_channel, en: T.smm_blocked_channel },
          user_inactive:           { ru: 'Канал не найден или недоступен. Проверьте, что канал публичный', ua: 'Канал не знайдено або недоступний. Перевірте, що канал публічний', en: 'Channel not found or unavailable. Make sure the channel is public' },
          neworder_invalid_link:   { ru: 'Неверная ссылка на канал', ua: 'Неправильне посилання на канал', en: 'Invalid channel link' },
          invalid_link:            { ru: 'Неверная ссылка', ua: 'Неправильне посилання', en: 'Invalid link' },
          reaction_not_configured: { ru: 'Эта реакция временно недоступна', ua: 'Ця реакція тимчасово недоступна', en: 'This reaction is temporarily unavailable' },
        }
        const key = Object.keys(smmErrMap).find(k => msg.toLowerCase().includes(k.toLowerCase()))
        if (msg === 'insufficient_balance') {
          setSmmError(lang === 'ru' ? 'Недостаточно звёзд — пополните баланс' : lang === 'ua' ? 'Недостатньо зірок — поповніть баланс' : 'Not enough stars — please top up')
        } else {
          const friendly = key ? (smmErrMap[key][lang] ?? smmErrMap[key]['ru']) : (lang === 'ru' ? 'Ошибка сервиса — попробуйте позже' : 'Помилка сервісу — спробуйте пізніше')
          setSmmError(friendly)
        }
      } finally { setSmmLoading(false) }
    }

    if (smmDone) return (
      <div className="page">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <button onClick={() => { setSmmDone(null); setView('smm_list') }} style={{
            width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--card2)', border: '1px solid var(--border)', cursor: 'pointer', fontSize: 20, color: 'var(--text2)', flexShrink: 0,
          }}>‹</button>
          <div style={{ fontWeight: 800, fontSize: 19 }}>{T.smm_accepted}</div>
        </div>
        <div className="smm-card" style={{ borderRadius: 24, padding: '40px 28px', textAlign: 'center', width: '100%' }}>
          <div style={{ fontSize: 60, marginBottom: 16, filter: 'drop-shadow(0 0 20px rgba(95,186,71,.5))' }}>✅</div>
          <div style={{ fontWeight: 800, fontSize: 22, marginBottom: 6 }}>{T.smm_accepted}</div>
          <div style={{
            display: 'inline-flex', gap: 10, alignItems: 'center',
            background: 'rgba(95,186,71,.12)', borderRadius: 20, padding: '5px 14px',
            fontSize: 13, color: '#7FD465', marginBottom: 18,
          }}>
            <span>#{smmDone.order_id}</span><span>·</span><span>⭐{smmDone.stars_spent}</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.6, marginBottom: 24 }}>{T.smm_start_soon}</div>
          <button className="btn btn-secondary" style={{ width: '100%' }}
            onClick={() => { setSmmDone(null); setSmmQty(100); setSmmCustom(''); setSmmLink('') }}>
            {T.smm_new_order}
          </button>
        </div>
      </div>
    )

    const infoItems = [
      { icon: '🔗', text: T.smm_info_link },
      { icon: '⛔️', text: T.smm_info_drop },
      { icon: '♻️', text: T.smm_info_warranty },
    ]

    const PRESETS = isViews ? [100, 500, 1000, 5000, 10000] : [10, 50, 100, 500, 1000]

    return (
      <div className="page">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
          <button onClick={() => setView('smm_list')} style={{
            width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--card2)', border: '1px solid var(--border)', cursor: 'pointer', fontSize: 20, color: 'var(--text2)', flexShrink: 0,
          }}>‹</button>
          <div>
            <div style={{ fontWeight: 800, fontSize: 19 }}>
              {isReactions ? '👎💩😱😢' : isViews ? '👁️' : '👥'}{' '}
              {isReactions ? T.smm_reactions_title : isViews ? T.smm_views_title : T.smm_subs_title}
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>Telegram</div>
          </div>
        </div>

        {/* Hero service card */}
        {svc && (
          <div className="smm-card" style={{ borderRadius: 20, padding: '16px 18px', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{
              width: 54, height: 54, borderRadius: 16, flexShrink: 0,
              background: 'linear-gradient(135deg, #5FBA47 0%, #2d7a1c 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26,
              boxShadow: '0 4px 14px rgba(95,186,71,.35)',
            }}>{isReactions ? '👎💩' : isViews ? '👁️' : '👥'}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 5 }}>
                {isReactions ? '👎💩😱😢 ' + T.smm_reactions_title : isViews ? T.smm_views_title : T.smm_subs_title}
              </div>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                background: 'rgba(95,186,71,.15)', border: '1px solid rgba(95,186,71,.3)',
                borderRadius: 20, padding: '2px 8px', fontSize: 11, fontWeight: 700, color: '#7FD465',
              }}>✅ {T.smm_guarantee}</span>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div className="text-green-grad" style={{ fontWeight: 900, fontSize: 20, lineHeight: 1 }}>⭐{isViews ? Math.round(svc.price_per_100_stars * 10) : svc.price_per_100_stars}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3 }}>{isViews ? T.smm_per_1000 : isReactions ? T.smm_per_100 : T.smm_per_100}</div>
            </div>
          </div>
        )}

        {/* Views warning */}
        {isViews && (
          <div style={{
            background: 'rgba(255,184,0,.07)', border: '1px solid rgba(255,184,0,.25)',
            borderRadius: 14, padding: '12px 14px', marginBottom: 14,
            fontSize: 12, color: 'var(--text2)', lineHeight: 1.6,
          }}>{T.smm_views_warning}</div>
        )}

        {/* Info block */}
        {!isViews && (
        <div style={{
          background: 'rgba(255,255,255,.025)', border: '1px solid rgba(255,255,255,.07)',
          borderRadius: 16, padding: '14px 16px', marginBottom: 16,
        }}>
          {infoItems.map((item, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: i < infoItems.length - 1 ? 10 : 0 }}>
              <span style={{ fontSize: 15, flexShrink: 0, lineHeight: 1.45 }}>{item.icon}</span>
              <span style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.5 }}>{item.text}</span>
            </div>
          ))}
        </div>
        )}

        {/* Form card */}
        <div style={{ background: 'var(--card)', border: '1px solid rgba(244,169,0,.22)', borderRadius: 20, padding: '18px 16px', boxShadow: '0 0 28px rgba(244,169,0,.06)' }}>


          {/* Link input */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8, marginBottom: 8 }}>
              {(isReactions || isViews ? T.smm_link_post_label : T.smm_link_label).toUpperCase()}
            </div>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: 13, top: '50%', transform: 'translateY(-50%)', fontSize: 16, pointerEvents: 'none', lineHeight: 1 }}>🔗</span>
              <input
                type="text"
                placeholder={isViews || isReactions ? T.smm_link_post_ph : 'https://t.me/yourchannel'}
                value={smmLink}
                onChange={e => setSmmLink(e.target.value)}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'var(--card2)',
                  border: '1.5px solid ' + (smmLink ? 'rgba(95,186,71,.45)' : 'var(--border)'),
                  borderRadius: 14, padding: '13px 14px 13px 40px',
                  color: 'var(--text)', fontSize: 14,
                  transition: 'border-color .2s',
                  outline: 'none',
                }}
              />
            </div>
          </div>

          {/* Quantity */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8 }}>
                {(isViews ? T.smm_qty_views_label : T.smm_qty_label).toUpperCase()}
              </div>
              <div style={{ fontWeight: 800, fontSize: 14, color: 'var(--text)' }}>
                {effectiveQty} <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--muted)' }}>{isViews ? T.smm_views_word : isReactions ? T.smm_reactions_word : T.smm_subs_word}</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 7, marginBottom: 10 }}>
              {PRESETS.map(q => (
                <button
                  key={q}
                  className={'qty-pill' + (effectiveQty === q && !smmCustom ? ' active' : '')}
                  onClick={() => { setSmmQty(q); setSmmCustom('') }}
                >{q >= 1000 ? `${q/1000}K` : q}</button>
              ))}
            </div>
            <input
              type="number" min={svc?.min ?? 10} max={svc?.max ?? 10000}
              value={smmCustom}
              onChange={e => {
                setSmmCustom(e.target.value)
                const min = svc?.min ?? 10
                const max = svc?.max ?? 10000
                const v = Math.max(min, Math.min(max, parseInt(e.target.value) || min))
                setSmmQty(v)
              }}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'var(--card2)',
                border: '1.5px solid ' + (smmCustom ? 'rgba(95,186,71,.4)' : 'var(--border)'),
                borderRadius: 12, padding: '11px 14px', color: 'var(--text)', fontSize: 14,
                outline: 'none', transition: 'border-color .2s',
              }}
              placeholder={T.smm_custom_ph}
            />
          </div>

          {/* Total cost */}
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            background: 'linear-gradient(135deg, rgba(244,169,0,.08) 0%, rgba(200,120,0,.05) 100%)',
            border: '1px solid rgba(244,169,0,.3)',
            borderRadius: 16, padding: '14px 18px', marginBottom: 16,
            boxShadow: '0 2px 16px rgba(244,169,0,.08)',
          }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 3 }}>{T.smm_total_label}</div>
              <div style={{ fontSize: 12, color: 'var(--text2)' }}>
                {effectiveQty} {isViews ? T.smm_views_word : isReactions ? T.smm_reactions_word : T.smm_subs_word}
                <span style={{ color: 'var(--muted)' }}> × ⭐{isViews ? Math.round((svc?.price_per_100_stars ?? 0) * 10) : svc?.price_per_100_stars}/{isViews ? 1000 : 100}</span>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div className="text-orange-grad" style={{ fontWeight: 900, fontSize: 30, lineHeight: 1 }}>⭐{priceStars}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3 }}>
                {T.smm_balance_label} ⭐{balance}
              </div>
            </div>
          </div>

          {smmError && (
            <div style={{
              background: 'rgba(255,68,68,.08)', border: '1px solid rgba(255,68,68,.25)',
              borderRadius: 12, padding: '11px 14px', fontSize: 13, color: '#ff7070', marginBottom: 10,
            }}>❌ {smmError}</div>
          )}
          {smmError && balance < priceStars && (
            <button className="btn btn-primary" style={{ width: '100%', marginBottom: 10 }} onClick={onGoToBalance}>
              {lang === 'ru' ? '💰 Пополнить баланс' : lang === 'ua' ? '💰 Поповнити баланс' : '💰 Top up balance'}
            </button>
          )}

          <button
            className={'btn btn-green' + (!canOrder || smmLoading ? ' btn-secondary' : '')}
            style={{ width: '100%', fontSize: 16, padding: '15px' }}
            disabled={!canOrder || smmLoading}
            onClick={orderSmm}
          >
            {smmLoading ? '⏳ ...' : smmLink.trim() ? `${T.smm_order_btn} — ⭐${priceStars}` : T.smm_enter_link}
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
      <p style={{ fontSize: 13, opacity: 0.55, margin: 0 }}>{T.buying_hint}</p>
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

      <div style={{
        background: 'rgba(42,171,238,.08)', border: '1px solid rgba(42,171,238,.25)',
        borderRadius: 14, padding: '14px 16px', fontSize: 13, color: 'var(--text2)',
        lineHeight: 1.6,
      }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: '#2AABEE', marginBottom: 4 }}>💾 Данные сохранены</div>
        Вы сможете повторно найти номер, получить код и просмотреть все детали заказа, зайдя во вкладку <b>Профиль → Мои аккаунты</b>.
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => { setResult(null); setCode(''); setView('menu') }}>
          {T.back}
        </button>
        {onGoToProfile && (
          <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => { setResult(null); setCode(''); onGoToProfile() }}>
            👤 В профиль
          </button>
        )}
      </div>
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

  // ─── NFT Юзернейми ────────────────────────────────────────────────────────
  if (view === 'nft') {
    const balance = me?.balance_stars ?? 0

    if (nftDone) {
      const expiresDate = new Date(nftDone.expires_at)
      const expiresStr = expiresDate.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
      const botUsername = me?.bot_username ?? 'lemur_shop_bot'
      return (
        <div className="page">
          <div style={{ textAlign: 'center', padding: '30px 0 20px' }}>
            <div style={{ fontSize: 64, marginBottom: 12, filter: 'drop-shadow(0 0 20px rgba(155,89,245,.6))' }}>✅</div>
            <div style={{ fontWeight: 800, fontSize: 22, marginBottom: 6 }}>Заказ #{nftDone.order_id} принят!</div>
            <div style={{ fontSize: 13, color: 'var(--muted)' }}>⭐{nftDone.stars_spent} списано с баланса</div>
          </div>

          <div style={{
            background: 'linear-gradient(135deg, #1a0d2e 0%, #130924 100%)',
            border: '1px solid rgba(160,80,255,.3)',
            borderRadius: 16, padding: '16px 18px', marginBottom: 16,
          }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#c084fc', marginBottom: 12 }}>📋 Как получить @{nftDone.username}:</div>
            <ol style={{ paddingLeft: 18, margin: 0, lineHeight: 2.1, fontSize: 13, color: 'var(--text2)' }}>
              <li>Напишите администратору: <b>@{botUsername}</b></li>
              <li>Укажите номер заказа: <b>#{nftDone.order_id}</b></li>
              <li>Администратор вручную передаст вам права на имя пользователя</li>
              <li>Срок аренды: <b>{nftDone.duration_days} дней</b> (до <b>{expiresStr}</b>)</li>
            </ol>
            <div style={{
              marginTop: 14, padding: '10px 14px', borderRadius: 10,
              background: 'rgba(255,200,0,.07)', border: '1px solid rgba(255,200,0,.2)',
              fontSize: 12, color: '#e0c060', lineHeight: 1.6,
            }}>
              ⚠️ Имя пользователя передаётся вручную в течение 24 часов после оплаты.
            </div>
          </div>

          <button className="btn btn-secondary" style={{ width: '100%' }} onClick={() => {
            setNftDone(null)
            setView('menu')
          }}>
            Назад в магазин
          </button>
        </div>
      )
    }

    return (
      <div className="page">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <button onClick={() => setView('menu')} style={{
            width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--card2)', border: '1px solid var(--border)', cursor: 'pointer', fontSize: 20, color: 'var(--text2)', flexShrink: 0,
          }}>‹</button>
          <div>
            <div style={{ fontWeight: 800, fontSize: 19 }}>@ NFT Юзернейми</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>Оренда Telegram-юзернеймів</div>
          </div>
        </div>

        {/* Search */}
        <div style={{ position: 'relative', marginBottom: 14 }}>
          <input
            type="text"
            placeholder="Пошук за юзернеймом..."
            value={nftSearchInput}
            onChange={e => handleNftSearchInput(e.target.value)}
            style={{
              width: '100%', padding: '11px 14px', borderRadius: 12,
              background: 'var(--card)', border: '1px solid var(--border)',
              color: 'var(--text)', fontSize: 14, boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Loading skeleton */}
        {nftLoading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{
                background: 'var(--card)', border: '1px solid var(--border)',
                borderRadius: 16, padding: '16px', height: 110,
                animation: 'pulse 1.5s infinite',
              }} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!nftLoading && nftItems.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--muted)' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
            <div style={{ fontSize: 15, fontWeight: 600 }}>Юзернеймів не знайдено</div>
          </div>
        )}

        {/* NFT grid */}
        {!nftLoading && nftItems.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {nftItems.map(nft => {
              const rented = nft.currently_rented
              const canBuy = !rented && balance >= nft.price_stars
              const isConfirming = nftConfirm?.id === nft.id
              const expiresDate = rented && nft.expires_at ? new Date(nft.expires_at).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' }) : null

              return (
                <div key={nft.id} style={{
                  background: 'linear-gradient(135deg, #1a0d2e 0%, #130924 100%)',
                  border: `1px solid ${rented ? 'rgba(255,80,80,.3)' : 'rgba(160,80,255,.25)'}`,
                  borderRadius: 16, padding: '16px 18px',
                  boxShadow: rented ? 'none' : '0 4px 18px rgba(140,60,255,.1)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div>
                      <div style={{ fontWeight: 900, fontSize: 20, fontFamily: 'monospace', color: rented ? 'var(--muted)' : '#c084fc' }}>
                        @{nft.username}
                      </div>
                      {nft.description && (
                        <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 3 }}>{nft.description}</div>
                      )}
                    </div>
                    <div style={{
                      padding: '4px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700,
                      background: rented ? 'rgba(255,80,80,.12)' : 'rgba(155,89,245,.15)',
                      color: rented ? '#ff7070' : '#c084fc',
                      border: `1px solid ${rented ? 'rgba(255,80,80,.3)' : 'rgba(155,89,245,.4)'}`,
                      flexShrink: 0, marginLeft: 10,
                    }}>
                      {rented ? 'Зайнятий 🔒' : 'Доступний ✅'}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 16, marginBottom: 12, fontSize: 12, color: 'var(--muted)' }}>
                    <span>⏳ на {nft.duration_days} днів</span>
                    {rented && expiresDate && <span style={{ color: '#ff9090' }}>до {expiresDate}</span>}
                  </div>

                  {isConfirming ? (
                    <div style={{
                      background: 'rgba(155,89,245,.1)', border: '1px solid rgba(155,89,245,.3)',
                      borderRadius: 12, padding: '12px 14px',
                    }}>
                      <div style={{ fontSize: 13, marginBottom: 10, color: 'var(--text2)' }}>
                        Підтвердити оренду <b>@{nft.username}</b> за <b>⭐{nft.price_stars}</b>?
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn btn-secondary" style={{ flex: 1, padding: '9px' }}
                          onClick={() => setNftConfirm(null)}>
                          Скасувати
                        </button>
                        <button
                          className="btn"
                          style={{ flex: 2, padding: '9px', background: 'linear-gradient(135deg,#9B59F5,#6A0DAD)', color: '#fff', fontWeight: 700 }}
                          disabled={nftBuying}
                          onClick={() => buyNft(nft)}
                        >
                          {nftBuying ? '⏳...' : `✅ Орендувати ⭐${nft.price_stars}`}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      className="btn"
                      style={{
                        width: '100%', padding: '10px',
                        background: rented || !canBuy
                          ? 'rgba(255,255,255,.06)'
                          : 'linear-gradient(135deg, #9B59F5, #6A0DAD)',
                        color: rented || !canBuy ? 'var(--muted)' : '#fff',
                        fontWeight: 700, cursor: rented || !canBuy ? 'not-allowed' : 'pointer',
                        border: '1px solid transparent',
                      }}
                      disabled={rented || !canBuy}
                      onClick={() => setNftConfirm(nft)}
                    >
                      {rented
                        ? 'Зайнятий 🔒'
                        : balance < nft.price_stars
                          ? `Недостатньо зірок (⭐${nft.price_stars})`
                          : `Орендувати ⭐${nft.price_stars}`}
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

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
