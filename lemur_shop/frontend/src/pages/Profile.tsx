import { useState, useEffect } from 'react'
import { api, type Me, type Order } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { me: Me | null; lang: Lang; onChangeLang: (l: Lang) => void }

const LANG_LABELS: Record<string, string> = {
  ru: '🇷🇺 Русский',
  ua: '🇺🇦 Українська',
  en: '🇬🇧 English',
}
const LANG_KEY = 'lemur_lang'

export const LEVELS = [
  { min: 0,   max: 4.99,     icon: '🌿', name: { ua: 'Новачок',     ru: 'Новичок',   en: 'Newbie'      }, discount: 0, color: '#52B788', glow: 'rgba(82,183,136,.45)' },
  { min: 5,   max: 14.99,    icon: '⚡', name: { ua: 'Активний',    ru: 'Активний',  en: 'Active'      }, discount: 1, color: '#4DA6E8', glow: 'rgba(77,166,232,.45)' },
  { min: 15,  max: 49.99,    icon: '🔥', name: { ua: 'Досвідчений', ru: 'Опытный',   en: 'Experienced' }, discount: 2, color: '#FF7B30', glow: 'rgba(255,123,48,.45)' },
  { min: 50,  max: 99.99,    icon: '💎', name: { ua: 'Преміум',     ru: 'Премиум',   en: 'Premium'     }, discount: 3, color: '#B77FFF', glow: 'rgba(183,127,255,.45)' },
  { min: 100, max: Infinity, icon: '👑', name: { ua: 'Легенда',     ru: 'Легенда',   en: 'Legend'      }, discount: 5, color: '#FFB830', glow: 'rgba(255,184,48,.50)' },
]

export function getLevel(n: number) { return LEVELS.find(l => n >= l.min && n <= l.max) ?? LEVELS[0] }
export function getLevelIdx(n: number) { return LEVELS.findIndex(l => n >= l.min && n <= l.max) }
export function getLevelDiscount(spentUsd: number): number { return getLevel(spentUsd).discount }

function getProgress(n: number) {
  const lvl = getLevel(n)
  if (lvl.max === Infinity) return 100
  const raw = ((n - lvl.min) / (lvl.max - lvl.min)) * 100
  return Math.max(raw, 12)
}

function needForNext(n: number) {
  const lvl = getLevel(n)
  if (lvl.max === Infinity) return null
  return lvl.max - n
}

const DISCOUNT_LABEL: Record<Lang, (d: number) => string> = {
  ua: d => d > 0 ? `Знижка ${d}% на покупки` : 'Знижки ще немає',
  ru: d => d > 0 ? `Скидка ${d}% на покупки` : 'Скидки пока нет',
  en: d => d > 0 ? `${d}% discount on purchases` : 'No discount yet',
}

function fmtLocal(usd: number, me: Me, lang: Lang): string {
  if (lang === 'ua' && me.rate_uah) return `${Math.round(usd * me.rate_uah)}₴`
  if (lang === 'ru' && me.rate_rub) return `${Math.round(usd * me.rate_rub)}₽`
  return usd.toFixed(2)
}

export default function Profile({ me, lang, onChangeLang }: Props) {
  const T = getT(lang)
  const [orders, setOrders] = useState<Order[]>([])
  const [loadingOrders, setLoadingOrders] = useState(true)
  const [openOrder, setOpenOrder] = useState<number | null>(null)
  const [codes, setCodes] = useState<Record<number, string>>({})
  const [gettingCode, setGettingCode] = useState<number | null>(null)
  const [copied, setCopied] = useState<string>('')

  useEffect(() => {
    api.orders().then(o => { setOrders(o); setLoadingOrders(false) }).catch(() => setLoadingOrders(false))
  }, [])

  function changeLang(l: Lang) {
    localStorage.setItem(LANG_KEY, l)
    api.setLang(l).catch(() => {})
    onChangeLang(l)
  }

  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(''), 2000)
    })
  }

  async function getCode(orderId: number) {
    setGettingCode(orderId)
    try {
      const res = await api.getCode(orderId)
      setCodes(prev => ({ ...prev, [orderId]: res.code }))
    } catch (e: any) {
      setCodes(prev => ({ ...prev, [orderId]: '❌ ' + (e.message ?? 'error') }))
    } finally {
      setGettingCode(null)
    }
  }

  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

  const usd = me.balance_usd
  const balanceLocal = lang === 'ua' && me.rate_uah
    ? `${Math.round(usd * me.rate_uah)}₴`
    : lang === 'ru' && me.rate_rub
    ? `${Math.round(usd * me.rate_rub)}₽`
    : ''

  const spent = me.total_spent_usd ?? 0
  const lvl = getLevel(spent)
  const lvlIdx = getLevelIdx(spent)
  const progress = getProgress(spent)
  const toNext = needForNext(spent)
  const nextLvl = LEVELS[lvlIdx + 1]

  return (
    <div className="page">

      {/* ── Balance + User in one hero card ── */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20,
        padding: '22px 18px 20px',
        marginBottom: 10,
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* bg glow */}
        <div style={{
          position: 'absolute', top: -40, right: -40,
          width: 180, height: 180, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,107,43,.15) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* User row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 16,
            background: `linear-gradient(135deg, ${lvl.color}50, ${lvl.color}20)`,
            border: `1.5px solid ${lvl.color}60`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, fontWeight: 800, color: '#fff', flexShrink: 0,
            boxShadow: `0 0 18px ${lvl.glow}`,
          }}>
            {me.name.charAt(0).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 17 }}>{me.name}</div>
            {me.username && <div className="muted" style={{ fontSize: 13, marginTop: 1 }}>@{me.username}</div>}
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontWeight: 800, fontSize: 20, color: 'var(--orange)' }}>{fmtLocal(spent, me, lang)}</div>
            <div className="muted" style={{ fontSize: 11 }}>
              {lang === 'ua' ? 'витрачено' : lang === 'ru' ? 'потрачено' : 'spent'}
            </div>
          </div>
        </div>

        {/* Balance */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 6 }}>
            {T.balance.toUpperCase()}
          </div>
          <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1 }}>
            {balanceLocal
              ? <>
                  <span style={{ fontWeight: 800, fontSize: 38 }}>{balanceLocal}</span>
                  <span style={{ fontWeight: 400, fontSize: 18, marginLeft: 10, color: 'var(--muted)' }}>${usd.toFixed(2)}</span>
                </>
              : <span style={{ fontWeight: 800, fontSize: 38 }}>${usd.toFixed(2)}</span>
            }
          </div>
        </div>

        {/* Level row */}
        <div style={{
          background: 'rgba(0,0,0,.25)',
          borderRadius: 14,
          padding: '14px 16px',
          border: `1px solid ${lvl.color}25`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 12,
              background: `${lvl.color}20`,
              border: `1.5px solid ${lvl.color}50`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20, flexShrink: 0,
              boxShadow: `0 0 14px ${lvl.glow}`,
            }}>
              {lvl.icon}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontWeight: 800, fontSize: 16, color: lvl.color }}>{lvl.name[lang]}</span>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
                  background: `${lvl.color}20`, color: lvl.color, border: `1px solid ${lvl.color}35`,
                }}>−{lvl.discount}%</span>
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                {DISCOUNT_LABEL[lang](lvl.discount)}
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span className="muted" style={{ fontSize: 11 }}>
              {fmtLocal(spent, me, lang)} / {lvl.max === Infinity ? '∞' : fmtLocal(lvl.max, me, lang)}
            </span>
            <span style={{ fontSize: 11, color: lvl.color, fontWeight: 700 }}>{Math.round(progress)}%</span>
          </div>
          <div style={{ height: 12, background: 'rgba(255,255,255,.06)', borderRadius: 8, overflow: 'hidden', marginBottom: 10 }}>
            <div style={{
              height: '100%', borderRadius: 8,
              width: `${progress}%`,
              background: `linear-gradient(90deg, ${lvl.color}80, ${lvl.color})`,
              transition: 'width .6s ease',
              position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', inset: 0,
                background: 'linear-gradient(90deg,transparent,rgba(255,255,255,.3),transparent)',
                animation: 'bar-shine 2s ease-in-out infinite',
              }} />
            </div>
          </div>

          {/* Level dots */}
          <div style={{ display: 'flex', gap: 5 }}>
            {LEVELS.map((l, i) => (
              <div key={i} style={{ flex: 1, textAlign: 'center' }}>
                <div style={{
                  height: 3, borderRadius: 3,
                  background: i <= lvlIdx ? l.color : 'rgba(255,255,255,.08)',
                  marginBottom: 4,
                  boxShadow: i <= lvlIdx ? `0 0 6px ${l.glow}` : 'none',
                  transition: 'background .3s',
                }} />
                <div style={{ fontSize: 16 }}>{l.icon}</div>
                <div style={{ fontSize: 9, color: i === lvlIdx ? l.color : 'var(--muted)', fontWeight: 700, marginTop: 2 }}>
                  {l.discount}%
                </div>
              </div>
            ))}
          </div>

          {toNext !== null && nextLvl && (
            <div className="muted" style={{ fontSize: 12, textAlign: 'center', marginTop: 10 }}>
              {T.to_next_lvl_usd(fmtLocal(toNext, me, lang), nextLvl.icon, nextLvl.name[lang])}
            </div>
          )}

          <div style={{ marginTop: 12, padding: '10px 12px', borderRadius: 10, background: 'rgba(255,184,48,.06)', border: '1px solid rgba(255,184,48,.15)' }}>
            <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>
              💡 {T.level_info}
            </div>
          </div>
        </div>
      </div>

      {/* ── Socials ── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 0 }}>
        <a href="https://t.me/LEMUR_SHOP" target="_blank" rel="noreferrer" style={{ flex: 1, textDecoration: 'none', minWidth: 0 }}>
          <div style={{
            background: 'linear-gradient(135deg, rgba(42,171,238,.12), rgba(17,120,184,.06))',
            border: '1px solid rgba(42,171,238,.22)',
            borderRadius: 14, padding: '12px 10px',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <div style={{
              width: 30, height: 30, borderRadius: 9, flexShrink: 0,
              background: 'linear-gradient(135deg, #2AABEE, #1178B8)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
            }}>📢</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 12, color: '#2AABEE', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>@LEMUR_SHOP</div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
                {lang === 'ua' ? 'Канал' : lang === 'ru' ? 'Канал' : 'Channel'}
              </div>
            </div>
          </div>
        </a>
        <a href="https://t.me/LEMUR_MANEGER" target="_blank" rel="noreferrer" style={{ flex: 1, textDecoration: 'none', minWidth: 0 }}>
          <div style={{
            background: 'linear-gradient(135deg, rgba(76,175,114,.1), rgba(76,175,114,.04))',
            border: '1px solid rgba(76,175,114,.22)',
            borderRadius: 14, padding: '12px 10px',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <div style={{
              width: 30, height: 30, borderRadius: 9, flexShrink: 0,
              background: 'linear-gradient(135deg, #4CAF72, #2e7a4e)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
            }}>💬</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 12, color: '#4CAF72', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>@LEMUR_MANEGER</div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
                {lang === 'ua' ? 'Підтримка' : lang === 'ru' ? 'Поддержка' : 'Support'}
              </div>
            </div>
          </div>
        </a>
      </div>

      {/* ── Language ── */}
      <div className="card" style={{ marginTop: 10 }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{T.change_lang}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['ru', 'ua', 'en'] as Lang[]).map(l => (
            <button
              key={l}
              className={`btn ${lang === l ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, padding: '9px 4px', fontSize: 13 }}
              onClick={() => changeLang(l)}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
      </div>

      {/* ── My accounts ── */}
      <div style={{ fontWeight: 700, fontSize: 15, margin: '16px 0 10px' }}>{T.my_accounts}</div>

      {loadingOrders ? (
        <>
          <div className="card"><div className="skeleton" style={{ height: 52 }} /></div>
          <div className="card"><div className="skeleton" style={{ height: 52 }} /></div>
        </>
      ) : orders.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--muted)', padding: '28px 16px' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
          {T.no_orders}
        </div>
      ) : (
        orders.map(o => {
          const phone = o.delivered_data || ''
          const isOpen = openOrder === o.id
          const orderCode = codes[o.id] || ''
          const isGetting = gettingCode === o.id

          return (
            <div key={o.id} className="card" style={{ marginBottom: 8, padding: 0, overflow: 'hidden' }}>
              <div
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', cursor: 'pointer' }}
                onClick={() => setOpenOrder(isOpen ? null : o.id)}
              >
                <div style={{
                  width: 36, height: 36, borderRadius: 10,
                  background: 'rgba(255,107,43,.12)', border: '1px solid rgba(255,107,43,.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18, flexShrink: 0,
                }}>📱</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>
                    {T.order_num} #{String(o.id).padStart(5, '0')}
                  </div>
                  <div className="muted" style={{ fontSize: 12, marginTop: 1 }}>
                    {new Date(o.created_at).toLocaleString(
                      lang === 'en' ? 'en-GB' : lang === 'ua' ? 'uk-UA' : 'ru-RU',
                      { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }
                    )} · ${o.price_usd.toFixed(2)}
                  </div>
                </div>
                <div style={{ color: 'var(--muted)', fontSize: 18, transition: 'transform .2s', transform: isOpen ? 'rotate(180deg)' : '' }}>▾</div>
              </div>

              {isOpen && phone && (
                <div style={{ borderTop: '1px solid var(--border)', padding: '14px 16px', background: 'var(--bg2)' }}>
                  <div style={{ marginBottom: 12 }}>
                    <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>📱 {T.your_phone}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <code style={{ flex: 1, fontSize: 15, fontWeight: 700 }}>{phone}</code>
                      <button className="btn btn-secondary" style={{ width: 'auto', padding: '6px 12px', fontSize: 12 }}
                        onClick={() => copy(phone, `phone-${o.id}`)}>
                        {copied === `phone-${o.id}` ? T.copied : T.copy}
                      </button>
                    </div>
                  </div>

                  <div style={{ background: 'rgba(255,107,43,.06)', border: '1px solid rgba(255,107,43,.12)', borderRadius: 10, padding: '10px 14px', marginBottom: 12, fontSize: 13 }}>
                    <ol style={{ paddingLeft: 16, lineHeight: 1.9, margin: 0, color: 'var(--text2)' }}>
                      <li>{T.step1}</li>
                      <li>{T.step2}: <code>{phone}</code></li>
                      <li>{T.step3}</li>
                      <li>{T.step4}</li>
                    </ol>
                  </div>

                  <div>
                    <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>🔑 {T.your_code}</div>
                    <button className="btn btn-primary" style={{ fontSize: 14, marginBottom: orderCode ? 10 : 0 }}
                      disabled={isGetting} onClick={() => getCode(o.id)}>
                      {isGetting ? T.getting_code : T.get_code}
                    </button>
                    {orderCode && !orderCode.startsWith('❌') && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                        <code style={{ flex: 1, fontSize: 24, fontWeight: 800, letterSpacing: 6 }}>{orderCode}</code>
                        <button className="btn btn-secondary" style={{ width: 'auto', padding: '6px 12px', fontSize: 12 }}
                          onClick={() => copy(orderCode, `code-${o.id}`)}>
                          {copied === `code-${o.id}` ? T.copied : T.copy}
                        </button>
                      </div>
                    )}
                    {orderCode && orderCode.startsWith('❌') && (
                      <p style={{ color: 'var(--red)', fontSize: 12, marginTop: 8 }}>{orderCode}</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })
      )}

      {me.is_admin && (
        <div className="card" style={{ textAlign: 'center', marginTop: 8, border: '1px solid rgba(255,184,48,.25)', background: 'rgba(255,184,48,.06)' }}>
          <span style={{ color: 'var(--gold)', fontWeight: 700 }}>⚙️ Admin</span>
        </div>
      )}
    </div>
  )
}
