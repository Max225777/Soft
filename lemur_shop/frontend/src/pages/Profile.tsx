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

const LEVELS = [
  { min: 0,  max: 2,  emoji: '🌱', name: { ua: 'Новачок',      ru: 'Новичок',    en: 'Newbie'    }, color: '#6CB86A' },
  { min: 3,  max: 9,  emoji: '⚡', name: { ua: 'Активний',     ru: 'Активный',   en: 'Active'    }, color: '#5BA3E0' },
  { min: 10, max: 24, emoji: '🔥', name: { ua: 'Досвідчений',  ru: 'Опытный',    en: 'Experienced'}, color: '#FF7B30' },
  { min: 25, max: 59, emoji: '💎', name: { ua: 'Преміум',      ru: 'Премиум',    en: 'Premium'   }, color: '#C77DFF' },
  { min: 60, max: Infinity, emoji: '👑', name: { ua: 'Легенда', ru: 'Легенда',   en: 'Legend'    }, color: '#FFB830' },
]

function getLevel(count: number) {
  return LEVELS.find(l => count >= l.min && count <= l.max) ?? LEVELS[0]
}

function getLevelProgress(count: number) {
  const lvl = getLevel(count)
  if (lvl.max === Infinity) return 100
  return Math.round(((count - lvl.min) / (lvl.max - lvl.min + 1)) * 100)
}

function getNextLevelName(count: number, lang: Lang) {
  const idx = LEVELS.findIndex(l => count >= l.min && count <= l.max)
  const next = LEVELS[idx + 1]
  if (!next) return null
  return `${next.emoji} ${next.name[lang]}`
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
    ? `(${Math.round(usd * me.rate_uah)}₴)`
    : lang === 'ru' && me.rate_rub
    ? `(${Math.round(usd * me.rate_rub)}₽)`
    : ''

  const lvl = getLevel(me.orders_count)
  const progress = getLevelProgress(me.orders_count)
  const nextName = getNextLevelName(me.orders_count, lang)

  return (
    <div className="page">

      {/* ── Balance ── */}
      <div className="card card-accent" style={{ textAlign: 'center', padding: '22px 16px', marginBottom: 10 }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 8, letterSpacing: .5 }}>
          {T.balance.toUpperCase()}
        </div>
        <div className="balance-glow" style={{ color: 'var(--orange)' }}>
          {balanceLocal
            ? <>
                <span style={{ fontWeight: 800, fontSize: 36 }}>{balanceLocal}</span>
                <span style={{ fontWeight: 400, fontSize: 18, marginLeft: 8, color: 'var(--muted)' }}>${usd.toFixed(2)}</span>
              </>
            : <span style={{ fontWeight: 800, fontSize: 36 }}>${usd.toFixed(2)}</span>
          }
        </div>
      </div>

      {/* ── User info + level ── */}
      <div className="card" style={{ padding: '18px 16px' }}>
        {/* Avatar + name */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
          <div style={{
            width: 54, height: 54, borderRadius: '50%',
            background: `linear-gradient(135deg, ${lvl.color}99, ${lvl.color}44)`,
            border: `2px solid ${lvl.color}60`,
            color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, fontWeight: 800, flexShrink: 0,
          }}>
            {me.name.charAt(0).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 17 }}>{me.name}</div>
            {me.username && <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>@{me.username}</div>}
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontWeight: 800, fontSize: 18, color: 'var(--orange)' }}>{me.orders_count}</div>
            <div className="muted" style={{ fontSize: 11 }}>покупок</div>
          </div>
        </div>

        <div className="divider" style={{ margin: '0 0 14px' }} />

        {/* Level block */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: `${lvl.color}18`,
            border: `1px solid ${lvl.color}40`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, flexShrink: 0,
          }}>
            {lvl.emoji}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 15, color: lvl.color }}>{lvl.name[lang]}</span>
              <span className="muted" style={{ fontSize: 12 }}>· {progress}%</span>
            </div>
            {nextName && (
              <div className="muted" style={{ fontSize: 12, marginTop: 1 }}>
                → {nextName}
              </div>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="level-bar-track">
          <div className="level-bar-fill" style={{ width: `${progress}%`, background: `linear-gradient(90deg, ${lvl.color}99, ${lvl.color})` }} />
        </div>

        {/* Level tiers */}
        <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
          {LEVELS.map((l, i) => {
            const current = getLevel(me.orders_count) === l
            return (
              <div key={i} style={{
                flex: 1, textAlign: 'center',
                padding: '5px 2px',
                borderRadius: 8,
                background: current ? `${l.color}18` : 'transparent',
                border: `1px solid ${current ? l.color + '50' : 'transparent'}`,
                transition: 'all .2s',
              }}>
                <div style={{ fontSize: 16 }}>{l.emoji}</div>
                <div style={{ fontSize: 9, color: current ? l.color : 'var(--muted)', fontWeight: current ? 700 : 400, marginTop: 2 }}>
                  {l.min}+
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Language ── */}
      <div className="card">
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
                  {/* Phone */}
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

                  {/* Instructions */}
                  <div style={{ background: 'rgba(255,107,43,.06)', border: '1px solid rgba(255,107,43,.12)', borderRadius: 10, padding: '10px 14px', marginBottom: 12, fontSize: 13 }}>
                    <ol style={{ paddingLeft: 16, lineHeight: 1.9, margin: 0, color: 'var(--text2)' }}>
                      <li>{T.step1}</li>
                      <li>{T.step2}: <code>{phone}</code></li>
                      <li>{T.step3}</li>
                      <li>{T.step4}</li>
                    </ol>
                  </div>

                  {/* Code */}
                  <div>
                    <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>🔑 {T.your_code}</div>
                    <button
                      className="btn btn-primary"
                      style={{ fontSize: 14, marginBottom: orderCode ? 10 : 0 }}
                      disabled={isGetting}
                      onClick={() => getCode(o.id)}
                    >
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
