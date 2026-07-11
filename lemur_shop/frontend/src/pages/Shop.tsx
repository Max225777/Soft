import { useState, useEffect, useRef } from 'react'
import { api, smmApi, type Category, type BuyResult, type Me, type SmmService, type NftItem } from '../api'
import { getT, type Lang } from '../i18n'
import LegalFooter from '../components/LegalFooter'

const REVIEWS_CHANNEL = 'LEMUR_SHOP_REP'
const REVIEWS_URL = `https://t.me/${REVIEWS_CHANNEL}`
const SELL_CHANNEL = 'LEMUR_SHOP_SELL'
const SELL_URL = `https://t.me/${SELL_CHANNEL}`
const REVIEWS_T: Record<Lang, { title: string; sub: string }> = {
  ru: { title: 'Отзывы', sub: 'отзывы покупателей' },
  ua: { title: 'Відгуки', sub: 'відгуки покупців' },
  en: { title: 'Reviews', sub: 'customer reviews' },
}
const SELL_T: Record<Lang, { title: string; sub: string }> = {
  ru: { title: 'Лента покупок', sub: 'покупки в реальном времени' },
  ua: { title: 'Стрічка покупок', sub: 'покупки в реальному часі' },
  en: { title: 'Purchase feed', sub: 'live purchases' },
}

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

// Ракета-«boost» — чіткий білий контур, читається як зростання, не як звук
const BOOST_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="26" height="26">
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>
    <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>
    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>
    <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>
  </svg>
)

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
          background: 'linear-gradient(160deg, #0C1220 0%, #08090F 100%)',
          border: '1px solid rgba(46,124,246,.3)',
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
                <span style={{ fontWeight: 800, fontSize: 24, color: 'var(--orange2)', lineHeight: 1 }}>⭐{cat.discount_stars}</span>
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

const ACC_INSTR_KEY = 'lemur_hide_acc_instruction'

const HERO_TEXT: Record<Lang, { t1: string; t2: string; steps: [string, string, string]; buyPill: string; catalog: string }> = {
  ru: { t1: 'Аккаунт Telegram', t2: 'за 2 минуты', steps: ['Выбери страну', 'Получи код', 'Пользуйся'], buyPill: 'Купить аккаунт', catalog: 'Каталог' },
  ua: { t1: 'Акаунт Telegram', t2: 'за 2 хвилини', steps: ['Вибери країну', 'Отримай код', 'Користуйся'], buyPill: 'Купити акаунт', catalog: 'Каталог' },
  en: { t1: 'Telegram account', t2: 'in 2 minutes', steps: ['Pick a country', 'Get the code', 'Enjoy'], buyPill: 'Buy account', catalog: 'Catalog' },
}

type CatSort = 'pop' | 'exp' | 'cheap' | 'az' | 'za'

const SORT_CHIPS: Record<Lang, { key: CatSort; label: string }[]> = {
  ru: [
    { key: 'pop', label: 'Популярные' }, { key: 'exp', label: 'Дороже' },
    { key: 'cheap', label: 'Дешевле' }, { key: 'az', label: 'От А' }, { key: 'za', label: 'От Я' },
  ],
  ua: [
    { key: 'pop', label: 'Популярні' }, { key: 'exp', label: 'Дорожче' },
    { key: 'cheap', label: 'Дешевше' }, { key: 'az', label: 'Від А' }, { key: 'za', label: 'Від Я' },
  ],
  en: [
    { key: 'pop', label: 'Popular' }, { key: 'exp', label: 'Price ↓' },
    { key: 'cheap', label: 'Price ↑' }, { key: 'az', label: 'A–Z' }, { key: 'za', label: 'Z–A' },
  ],
}

const SEARCH_PH: Record<Lang, string> = {
  ru: 'Найти страну',
  ua: 'Знайти країну',
  en: 'Search country',
}

const SEARCH_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="11" cy="11" r="7"/>
    <path d="M21 21l-4.35-4.35"/>
  </svg>
)

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
  const [catSearch, setCatSearch] = useState('')
  const [catSort, setCatSort] = useState<CatSort>('pop')
  const buyingRef = useRef(false)
  // Інструкція під час покупки акаунта (перекриває час завантаження)
  const [instrAck, setInstrAck] = useState(false)
  const [instrReady, setInstrReady] = useState(false)  // показуємо інструкцію лише коли покупка точно пішла (не миттєва помилка балансу)
  const [pendingBuy, setPendingBuy] = useState<BuyResult | null>(null)
  const [dontShowInstr, setDontShowInstr] = useState(false)
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
    // Якщо юзер не відключив інструкцію — показуємо її поверх завантаження
    const optedOut = localStorage.getItem(ACC_INSTR_KEY) === '1'
    setInstrAck(optedOut)
    setDontShowInstr(false)
    setPendingBuy(null)
    setInstrReady(false)
    setView('buying')
    setCode('')
    // Інструкцію показуємо тільки якщо через ~0.5с покупка ще триває (тобто це
    // не миттєва помилка недостатнього балансу). Якщо view вже не 'buying' —
    // умова рендера сама її не покаже.
    setTimeout(() => setInstrReady(true), 500)
    try {
      const res = await api.buy(cat.category)
      setPendingBuy(res)
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

  // Показуємо результат покупки лише після того, як юзер ознайомився з інструкцією
  // (і акаунт уже куплений). Інструкція йде паралельно із завантаженням.
  useEffect(() => {
    if (view === 'buying' && instrAck && pendingBuy) {
      setResult(pendingBuy)
      setPendingBuy(null)
      setView('success')
    }
  }, [view, instrAck, pendingBuy])

  function ackInstruction() {
    if (dontShowInstr) {
      try { localStorage.setItem(ACC_INSTR_KEY, '1') } catch { /* ignore */ }
    }
    setInstrAck(true)
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
    const H = HERO_TEXT[lang]

    return (
      <div className="page">
        {/* Top bar: маленький баланс у кутку */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
          <div className="balance-glow" style={{
            display: 'inline-flex', alignItems: 'baseline', gap: 5,
            background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 999, padding: '7px 13px',
          }}>
            <span style={{ fontWeight: 800, fontSize: 15, color: 'var(--orange2)' }}>⭐{starsBalance}</span>
            <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--muted)' }}>${usdDisplay}</span>
          </div>
        </div>

        {/* Hero */}
        <div style={{ padding: '8px 0 18px', textAlign: 'center' }}>
          <div className="display" style={{ fontSize: 26, color: 'var(--text)' }}>
            {H.t1}
            <br />
            <span style={{
              background: 'linear-gradient(120deg, #7DB4FF, #2AABEE)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
            }}>{H.t2}</span>
          </div>
        </div>

        {/* Кроки 1-2-3 */}
        <div className="steps-row">
          {[0, 1, 2].map(i => (
            <div key={i} style={{ flex: 1, minWidth: 0 }}>
              <div className="step-card">
                <div className="step-num">{i + 1}</div>
                {i === 0 && (
                  <div style={{
                    background: 'rgba(255,255,255,.92)', color: '#0A0A0F',
                    borderRadius: 999, padding: '7px 10px',
                    fontSize: 10.5, fontWeight: 800, whiteSpace: 'nowrap',
                    boxShadow: '0 4px 14px rgba(0,0,0,.35)',
                  }}>{H.buyPill}</div>
                )}
                {i === 1 && (
                  <div style={{ display: 'flex', gap: 4 }}>
                    {['4', '•', '•', '1'].map((d, j) => (
                      <div key={j} style={{
                        width: 20, height: 26, borderRadius: 6,
                        background: 'rgba(255,255,255,.92)', color: '#0A0A0F',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 13, fontWeight: 800,
                        boxShadow: '0 4px 14px rgba(0,0,0,.35)',
                      }}>{d}</div>
                    ))}
                  </div>
                )}
                {i === 2 && (
                  <div style={{
                    width: 42, height: 42, borderRadius: '50%',
                    background: 'rgba(255,255,255,.92)', color: '#0A0A0F',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 15, fontWeight: 900, letterSpacing: 1,
                    boxShadow: '0 4px 14px rgba(0,0,0,.35)',
                  }}>···</div>
                )}
              </div>
              <div className="step-caption">{H.steps[i]}</div>
            </div>
          ))}
        </div>

        <div style={{ height: 14 }} />

        {/* Дві плашки поруч: чат з відгуками (ліва) і чат зі стрічкою покупок (права) */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
          {/* Відгуки */}
          <a href={REVIEWS_URL} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
            <div style={{
              background: 'linear-gradient(135deg, rgba(42,171,238,.1), rgba(46,124,246,.03))',
              border: '1px solid rgba(42,171,238,.28)',
              borderRadius: 18, padding: '14px 14px', height: '100%',
              display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              <div style={{
                width: 42, height: 42, borderRadius: 13, flexShrink: 0, marginBottom: 6,
                background: 'linear-gradient(135deg, #2AABEE, #1178B8)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 21,
              }}>⭐</div>
              <div style={{ fontWeight: 800, fontSize: 15, color: 'var(--text)' }}>{REVIEWS_T[lang].title}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.3 }}>{REVIEWS_T[lang].sub}</div>
              <div style={{ fontSize: 11.5, fontWeight: 700, color: '#7DB4FF', marginTop: 'auto', paddingTop: 8 }}>@{REVIEWS_CHANNEL} ›</div>
            </div>
          </a>

          {/* Стрічка покупок */}
          <a href={SELL_URL} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
            <div style={{
              background: 'linear-gradient(135deg, rgba(51,208,122,.1), rgba(51,208,122,.03))',
              border: '1px solid rgba(51,208,122,.28)',
              borderRadius: 18, padding: '14px 14px', height: '100%',
              display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              <div style={{
                width: 42, height: 42, borderRadius: 13, flexShrink: 0, marginBottom: 6,
                background: 'linear-gradient(135deg, #33D07A, #1FA85E)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 21,
              }}>🛒</div>
              <div style={{ fontWeight: 800, fontSize: 15, color: 'var(--text)' }}>{SELL_T[lang].title}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.3 }}>{SELL_T[lang].sub}</div>
              <div style={{ fontSize: 11.5, fontWeight: 700, color: '#33D07A', marginTop: 'auto', paddingTop: 8 }}>@{SELL_CHANNEL} ›</div>
            </div>
          </a>
        </div>

        <h1 style={{ marginBottom: 12 }}>{H.catalog}</h1>

        {/* TG Accounts card */}
        <div style={{
          background: 'radial-gradient(130% 100% at 15% 0%, rgba(46,124,246,.18) 0%, transparent 55%), var(--card)',
          border: '1px solid rgba(46,124,246,.28)',
          borderRadius: 20, padding: '18px 16px', marginBottom: 10,
          boxShadow: '0 8px 30px rgba(20,60,150,.18)',
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 16, flexShrink: 0,
              background: 'linear-gradient(135deg, #2AABEE, #2E7CF6)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(46,124,246,.35)', color: '#fff',
            }}>{TG_ICON}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_accounts}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>{T.tg_accounts_desc}</div>
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => setView('list')} style={{
            width: '100%', padding: '12px', fontSize: 14,
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
              background: 'linear-gradient(135deg, #17C0C9, #0E8FA8)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(23,192,201,.35)',
              border: '1px solid rgba(255,255,255,.14)',
            }}>{BOOST_ICON}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 17 }}>{T.tg_boost}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>{T.tg_boost_desc}</div>
            </div>
          </div>
          <button className="btn btn-primary" onClick={() => setView('smm_list')} style={{
            width: '100%', padding: '12px', fontSize: 14,
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
  if (view === 'list') {
    const catTitle = (c: Category) => (lang === 'ru' ? c.title_ru : lang === 'ua' ? c.title_ua : c.title) || c.title
    const effPrice = (c: Category) => c.discount_stars || c.price_stars
    const q = catSearch.trim().toLowerCase()
    const shown = cats
      .filter(c => !q || catTitle(c).toLowerCase().includes(q) || (c.phone_prefix ?? '').includes(q))
      .sort((a, b) => {
        switch (catSort) {
          case 'exp':   return effPrice(b) - effPrice(a)
          case 'cheap': return effPrice(a) - effPrice(b)
          case 'az':    return catTitle(a).localeCompare(catTitle(b), lang === 'en' ? 'en' : 'ru')
          case 'za':    return catTitle(b).localeCompare(catTitle(a), lang === 'en' ? 'en' : 'ru')
          default:      return 0
        }
      })

    return (
    <>
      {confirmCat && (
        <ConfirmModal
          cat={confirmCat} me={me} lang={lang}
          onConfirm={() => buy(confirmCat)}
          onCancel={() => setConfirmCat(null)}
        />
      )}
      <div className="page">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <button onClick={() => setView('menu')} style={{
            width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--card2)', border: '1px solid var(--border)', cursor: 'pointer', fontSize: 20, color: 'var(--text2)', flexShrink: 0,
          }}>‹</button>
          <h1 style={{ margin: 0 }}>{T.tg_accounts}</h1>
        </div>

        {/* Search */}
        <div className="search-wrap">
          {SEARCH_ICON}
          <input
            className="search-input"
            type="text"
            placeholder={SEARCH_PH[lang]}
            value={catSearch}
            onChange={e => setCatSearch(e.target.value)}
          />
        </div>

        {/* Sort chips */}
        <div className="chips-row">
          {SORT_CHIPS[lang].map(c => (
            <button
              key={c.key}
              className={'chip' + (catSort === c.key ? ' active' : '')}
              onClick={() => setCatSort(c.key)}
            >{c.label}</button>
          ))}
        </div>

        {cats.length === 0 ? (
          <>
            <div className="card"><div className="skeleton" style={{ height: 60 }} /></div>
            <div className="card"><div className="skeleton" style={{ height: 60 }} /></div>
          </>
        ) : (
          <>
            {cats.some(c => c.discount_stars) && (
              <div style={{
                fontSize: 12, fontWeight: 700, color: '#7DB4FF',
                background: 'rgba(46,124,246,.1)', border: '1px solid rgba(46,124,246,.28)',
                borderRadius: 12, padding: '9px 14px', textAlign: 'center', marginBottom: 10,
              }}>
                🎉 Акция открытия магазина — скидки на все аккаунты
              </div>
            )}
            {shown.length === 0 && (
              <div style={{ textAlign: 'center', padding: '36px 20px', color: 'var(--muted)' }}>
                <div style={{ fontSize: 36, marginBottom: 10 }}>🔍</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>
                  {lang === 'ru' ? 'Ничего не найдено' : lang === 'ua' ? 'Нічого не знайдено' : 'Nothing found'}
                </div>
              </div>
            )}
            {shown.map(cat => (
              <div key={cat.category} className="card" style={{ padding: '14px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{
                    width: 52, height: 52, borderRadius: 16, flexShrink: 0,
                    background: 'var(--card2)', border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 28, lineHeight: 1,
                  }}>{cat.flag}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 800, fontSize: 15 }}>
                      {catTitle(cat)}
                      {cat.phone_prefix && (
                        <span style={{ fontWeight: 400, fontSize: 12, color: 'var(--muted)', marginLeft: 6 }}>
                          ({cat.phone_prefix})
                        </span>
                      )}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 13 }}>
                      {cat.discount_stars ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                          <span style={{ textDecoration: 'line-through', color: 'var(--muted)', fontSize: 11 }}>⭐{cat.price_stars}</span>
                          <span style={{ fontWeight: 800, color: 'var(--orange2)', fontSize: 14 }}>⭐{cat.discount_stars}</span>
                          <span style={{ color: 'var(--muted)', fontSize: 11 }}>(${(cat.discount_stars * 0.013).toFixed(2)})</span>
                        </span>
                      ) : (
                        <span style={{ color: 'var(--orange2)' }}>{localPrice(cat.price_stars, cat.price_usd)}</span>
                      )}
                    </div>
                  </div>
                  <button
                    className="btn btn-primary"
                    style={{ width: 'auto', padding: '10px 20px', fontSize: 13.5, flexShrink: 0 }}
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
  }

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
                background: isReactCard ? 'linear-gradient(135deg, #2d2200, #3a2e00)' : 'linear-gradient(135deg, #2AABEE, #2E7CF6)',
                border: isReactCard ? '1px solid rgba(244,169,0,.3)' : 'none',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: isReactCard ? 20 : (isViews ? 0 : 25),
                boxShadow: isReactCard ? '0 4px 14px rgba(244,169,0,.25)' : '0 4px 14px rgba(46,124,246,.4)',
                color: '#fff',
              }}>
                {isReactCard ? '😊' : isViews ? EYE_ICON : '👥'}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 800, fontSize: 15 }}>{cardTitle}</div>
                {!isReactCard && !isViews && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 5, fontWeight: 700, fontSize: 12, color: '#7DB4FF' }}>
                    <span style={{ fontSize: 14 }}>♻️</span>
                    <span>{T.smm_guarantee}</span>
                  </div>
                )}
                {cardSub}
              </div>

              {/* Right price badge */}
              <div style={{
                flexShrink: 0,
                background: 'var(--card2)',
                border: '1px solid rgba(245,181,10,.3)',
                borderRadius: 16, padding: '13px 15px',
                textAlign: 'center',
              }}>
                <div style={{ fontWeight: 900, fontSize: 18, color: 'var(--text)', lineHeight: 1 }}>{badgeQty}</div>
                <div style={{ fontWeight: 700, fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', marginTop: 2 }}>{badgeWord}</div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,.2)', margin: '4px 0' }}>——</div>
                <div style={{ fontWeight: 900, fontSize: 22, color: 'var(--orange2)', lineHeight: 1 }}>⭐{badgeStars}</div>
              </div>

              <div style={{ color: '#7DB4FF', fontSize: 18, fontWeight: 300, flexShrink: 0 }}>›</div>
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
          <div style={{ fontSize: 60, marginBottom: 16, filter: 'drop-shadow(0 0 20px rgba(46,124,246,.5))' }}>✅</div>
          <div style={{ fontWeight: 800, fontSize: 22, marginBottom: 6 }}>{T.smm_accepted}</div>
          <div style={{
            display: 'inline-flex', gap: 10, alignItems: 'center',
            background: 'rgba(46,124,246,.12)', borderRadius: 20, padding: '5px 14px',
            fontSize: 13, color: '#7DB4FF', marginBottom: 18,
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
                      border: active ? '2px solid rgba(46,124,246,.7)' : '2px solid var(--border)',
                      background: active ? 'linear-gradient(135deg, rgba(46,124,246,.16), rgba(42,171,238,.08))' : 'var(--card2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      transition: 'all .15s',
                      boxShadow: active ? '0 0 16px rgba(46,124,246,.25)' : 'none',
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
                    border: active ? '2px solid rgba(46,124,246,.8)' : '2px solid rgba(255,255,255,.12)',
                    background: active
                      ? 'linear-gradient(135deg, rgba(46,124,246,.18), rgba(42,171,238,.10))'
                      : 'linear-gradient(135deg, rgba(255,255,255,.06), rgba(255,255,255,.02))',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                    transition: 'all .15s',
                    boxShadow: active ? '0 0 18px rgba(46,124,246,.3)' : '0 0 0 rgba(0,0,0,0)',
                  }}>
                  <span style={{ fontSize: 18, letterSpacing: 1 }}>{btn.emoji}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Form card */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 20, padding: '18px 16px' }}>

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
                  border: '1.5px solid ' + (smmLink ? 'rgba(46,124,246,.45)' : 'var(--border)'),
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
                border: '1.5px solid ' + (smmCustom ? 'rgba(46,124,246,.4)' : 'var(--border)'),
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
          <div style={{ fontSize: 60, marginBottom: 16, filter: 'drop-shadow(0 0 20px rgba(46,124,246,.5))' }}>✅</div>
          <div style={{ fontWeight: 800, fontSize: 22, marginBottom: 6 }}>{T.smm_accepted}</div>
          <div style={{
            display: 'inline-flex', gap: 10, alignItems: 'center',
            background: 'rgba(46,124,246,.12)', borderRadius: 20, padding: '5px 14px',
            fontSize: 13, color: '#7DB4FF', marginBottom: 18,
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
              background: 'linear-gradient(135deg, #2AABEE 0%, #2E7CF6 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26,
              boxShadow: '0 4px 14px rgba(46,124,246,.35)',
            }}>{isReactions ? '👎💩' : isViews ? '👁️' : '👥'}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 5 }}>
                {isReactions ? '👎💩😱😢 ' + T.smm_reactions_title : isViews ? T.smm_views_title : T.smm_subs_title}
              </div>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                background: 'rgba(46,124,246,.15)', border: '1px solid rgba(46,124,246,.3)',
                borderRadius: 20, padding: '2px 8px', fontSize: 11, fontWeight: 700, color: '#7DB4FF',
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
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 20, padding: '18px 16px' }}>


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
                  border: '1.5px solid ' + (smmLink ? 'rgba(46,124,246,.45)' : 'var(--border)'),
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
                border: '1.5px solid ' + (smmCustom ? 'rgba(46,124,246,.4)' : 'var(--border)'),
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
  if (view === 'buying' && !instrAck && instrReady) return (
    <div className="page">
      <div style={{
        background: 'linear-gradient(135deg, #0d1520 0%, #111a2e 100%)',
        border: '1px solid rgba(42,171,238,.25)', borderRadius: 20, padding: '20px 18px', marginTop: 8,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <div style={{ fontSize: 30 }}>📘</div>
          <div style={{ fontWeight: 800, fontSize: 17 }}>Инструкция по использованию</div>
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text2)' }}>
          Здравствуйте! Это инструкция по использованию TG-аккаунтов.
          <div style={{ marginTop: 12, fontWeight: 700, color: '#4ade80' }}>✅ В первые 24 часа после входа можно:</div>
          <div style={{ marginTop: 4 }}>1. Ставить 2FA (двухфакторную защиту)</div>
          <div>2. Привязывать почту для входа</div>
          <div style={{ marginTop: 12, fontWeight: 700, color: '#ef4444' }}>⛔ Нельзя:</div>
          <div style={{ marginTop: 4 }}>1. Ставить аватарки, юзернеймы, имена — вообще менять данные аккаунта</div>
          <div>2. Писать кому-то первым или вести подозрительную активность</div>
          <div style={{
            marginTop: 14, padding: '10px 12px', borderRadius: 10,
            background: 'rgba(255,180,40,.1)', border: '1px solid rgba(255,180,40,.3)',
            fontWeight: 700, color: '#FFD166',
          }}>
            🌐 Вход на аккаунт — только через VPN/прокси страны аккаунта!
          </div>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 16, cursor: 'pointer', fontSize: 13, color: 'var(--muted)' }}>
          <input type="checkbox" checked={dontShowInstr} onChange={e => setDontShowInstr(e.target.checked)} style={{ width: 16, height: 16 }} />
          Больше не показывать инструкцию
        </label>

        <button className="btn btn-primary" onClick={ackInstruction} style={{ width: '100%', marginTop: 14, fontSize: 15, fontWeight: 800 }}>
          Ознакомлен ✓
        </button>
        {!pendingBuy && (
          <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--muted)', marginTop: 10 }}>
            ⏳ Аккаунт готовится, пока читаете…
          </div>
        )}
      </div>
    </div>
  )

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
