import { useState, useEffect } from 'react'
import { api, type Order } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang }

const COUNTRY_FLAGS: Record<string, string> = {
  us: '🇺🇸', ua: '🇺🇦', kz: '🇰🇿', mm: '🇲🇲',
  co: '🇨🇴', de: '🇩🇪', ru: '🇷🇺', gb: '🇬🇧',
  fr: '🇫🇷', pl: '🇵🇱', br: '🇧🇷', in: '🇮🇳',
}
const COUNTRY_NAMES: Record<string, Record<string, string>> = {
  us: { ru: 'США',       ua: 'США',       en: 'USA' },
  ua: { ru: 'Украина',   ua: 'Україна',   en: 'Ukraine' },
  kz: { ru: 'Казахстан', ua: 'Казахстан', en: 'Kazakhstan' },
  mm: { ru: 'Мьянма',    ua: "М'янма",    en: 'Myanmar' },
  co: { ru: 'Колумбия',  ua: 'Колумбія',  en: 'Colombia' },
  de: { ru: 'Германия',  ua: 'Німеччина', en: 'Germany' },
  ru: { ru: 'Россия',    ua: 'Росія',     en: 'Russia' },
  gb: { ru: 'Британия',  ua: 'Британія',  en: 'UK' },
  fr: { ru: 'Франция',   ua: 'Франція',   en: 'France' },
  pl: { ru: 'Польша',    ua: 'Польща',    en: 'Poland' },
  br: { ru: 'Бразилия',  ua: 'Бразилія',  en: 'Brazil' },
  in: { ru: 'Индия',     ua: 'Індія',     en: 'India' },
}
const SMM_LABELS: Record<string, string> = {
  tg_subscribers: '👥 Підписники',
  tg_views:       '👁 Перегляди',
  tg_reactions:   '⚡ Реакції',
}

function categoryLabel(o: Order, lang: string): { icon: string; label: string; isAccount: boolean } {
  if (!o.category || o.category in COUNTRY_FLAGS || (!o.category.startsWith('tg_') && COUNTRY_FLAGS[o.category])) {
    const cat = o.category || ''
    const flag = COUNTRY_FLAGS[cat] || '📱'
    const name = COUNTRY_NAMES[cat]?.[lang] || COUNTRY_NAMES[cat]?.['ru'] || cat.toUpperCase()
    return { icon: flag, label: `TG-акаунт ${name}`, isAccount: true }
  }
  if (o.category.startsWith('tg_react')) return { icon: '⚡', label: 'Реакція', isAccount: false }
  const smm = SMM_LABELS[o.category]
  if (smm) {
    const [icon, ...rest] = smm.split(' ')
    return { icon, label: rest.join(' '), isAccount: false }
  }
  return { icon: '📱', label: o.category.toUpperCase(), isAccount: true }
}

export default function Orders({ lang }: Props) {
  const T = getT(lang)
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [openOrder, setOpenOrder] = useState<number | null>(null)
  const [codes, setCodes] = useState<Record<number, string>>({})
  const [gettingCode, setGettingCode] = useState<number | null>(null)
  const [copied, setCopied] = useState<string>('')

  useEffect(() => {
    api.orders().then(o => { setOrders(o); setLoading(false) }).catch(() => setLoading(false))
  }, [])

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

  const locale = lang === 'en' ? 'en-GB' : lang === 'ua' ? 'uk-UA' : 'ru-RU'

  return (
    <div className="page">
      <div style={{ fontWeight: 800, fontSize: 20, marginBottom: 16 }}>
        {lang === 'ru' ? '📋 Мои заказы' : lang === 'ua' ? '📋 Мої замовлення' : '📋 My Orders'}
      </div>

      {loading ? (
        <>
          {[1,2,3].map(i => <div key={i} className="card" style={{ marginBottom: 8 }}><div className="skeleton" style={{ height: 52 }} /></div>)}
        </>
      ) : orders.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--muted)', padding: '36px 16px' }}>
          <div style={{ fontSize: 40, marginBottom: 10 }}>📭</div>
          <div style={{ fontWeight: 600 }}>{T.no_orders}</div>
        </div>
      ) : (
        orders.map(o => {
          const phone = o.delivered_data || ''
          const isOpen = openOrder === o.id
          const orderCode = codes[o.id] || ''
          const isGetting = gettingCode === o.id
          const priceStars = Math.round(o.price_usd / 0.013)
          const { icon, label, isAccount } = categoryLabel(o, lang)

          return (
            <div key={o.id} style={{
              marginBottom: 10, borderRadius: 16, overflow: 'hidden',
              background: 'var(--bg2)',
              border: isAccount ? '1px solid rgba(255,107,43,.2)' : '1px solid rgba(42,171,238,.15)',
              boxShadow: '0 2px 12px rgba(0,0,0,.18)',
            }}>
              <div
                style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', cursor: isAccount ? 'pointer' : 'default' }}
                onClick={() => isAccount && setOpenOrder(isOpen ? null : o.id)}
              >
                {/* Icon */}
                <div style={{
                  width: 44, height: 44, borderRadius: 13, flexShrink: 0,
                  background: isAccount ? 'linear-gradient(135deg, rgba(255,107,43,.2), rgba(255,107,43,.08))' : 'linear-gradient(135deg, rgba(42,171,238,.2), rgba(42,171,238,.08))',
                  border: isAccount ? '1.5px solid rgba(255,107,43,.3)' : '1.5px solid rgba(42,171,238,.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 22,
                }}>{icon}</div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>
                    {isAccount && <span style={{ opacity: .6, fontSize: 12 }}>Telegram · </span>}{label}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <span>{new Date(o.created_at).toLocaleString(locale, { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
                    <span>·</span><span>⭐{priceStars}</span>
                    {o.smm_quantity > 0 && <><span>·</span><span>{o.smm_quantity} шт.</span></>}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{
                    fontSize: 11, fontWeight: 700, padding: '4px 9px', borderRadius: 8,
                    background: o.status === 'delivered' ? 'rgba(76,175,114,.15)' : o.status === 'pending' ? 'rgba(255,184,48,.12)' : 'rgba(255,107,43,.12)',
                    color: o.status === 'delivered' ? '#4CAF72' : o.status === 'pending' ? '#FFB830' : 'var(--orange)',
                  }}>
                    {o.status === 'delivered' ? '✓ Виконано' : o.status === 'pending' ? '⏳' : o.status}
                  </div>
                  {isAccount && (
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: isOpen ? 'rgba(255,107,43,.2)' : 'rgba(255,255,255,.06)',
                      border: isOpen ? '1px solid rgba(255,107,43,.4)' : '1px solid var(--border)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 13, color: isOpen ? 'var(--orange)' : 'var(--muted)',
                      transition: 'all .2s', transform: isOpen ? 'rotate(180deg)' : '',
                      flexShrink: 0,
                    }}>▼</div>
                  )}
                </div>
              </div>

              {isOpen && isAccount && (
                <div style={{ borderTop: '1px solid rgba(255,107,43,.15)', padding: '16px', background: 'rgba(255,107,43,.03)' }}>
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
                    {orderCode?.startsWith('❌') && (
                      <p style={{ color: 'var(--red)', fontSize: 12, marginTop: 8 }}>{orderCode}</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}
