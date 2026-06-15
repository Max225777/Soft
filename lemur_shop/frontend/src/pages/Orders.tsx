import { useState, useEffect } from 'react'
import { api, type Order } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang }

const SMM_LABELS: Record<string, string> = {
  tg_subscribers: '👥 Підписники',
  tg_views:       '👁 Перегляди',
  tg_reactions:   '⚡ Реакції',
}

function categoryLabel(o: Order): string {
  if (!o.category) return '📱 Акаунт'
  const smm = SMM_LABELS[o.category]
  if (smm) return smm
  if (o.category.startsWith('tg_react')) return '⚡ Реакція'
  return `📱 ${o.category.toUpperCase()}`
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
          const isAccount = !!phone
          const priceStars = Math.round(o.price_usd / 0.013)
          const label = categoryLabel(o)

          return (
            <div key={o.id} className="card" style={{ marginBottom: 8, padding: 0, overflow: 'hidden' }}>
              <div
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', cursor: isAccount ? 'pointer' : 'default' }}
                onClick={() => isAccount && setOpenOrder(isOpen ? null : o.id)}
              >
                <div style={{
                  width: 38, height: 38, borderRadius: 11,
                  background: isAccount ? 'rgba(255,107,43,.12)' : 'rgba(42,171,238,.1)',
                  border: isAccount ? '1px solid rgba(255,107,43,.2)' : '1px solid rgba(42,171,238,.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18, flexShrink: 0,
                }}>{isAccount ? '📱' : '⚡'}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{label}</div>
                  <div className="muted" style={{ fontSize: 12, marginTop: 1 }}>
                    {new Date(o.created_at).toLocaleString(locale, { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    {' · '}⭐{priceStars}
                    {o.smm_quantity > 0 && ` · ${o.smm_quantity} шт.`}
                  </div>
                </div>
                <div style={{
                  fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 7,
                  background: o.status === 'delivered' ? 'rgba(76,175,114,.15)' : o.status === 'pending' ? 'rgba(255,184,48,.12)' : 'rgba(255,107,43,.12)',
                  color: o.status === 'delivered' ? '#4CAF72' : o.status === 'pending' ? '#FFB830' : 'var(--orange)',
                }}>
                  {o.status === 'delivered' ? '✓' : o.status === 'pending' ? '⏳' : o.status}
                </div>
                {isAccount && (
                  <div style={{ color: 'var(--muted)', fontSize: 18, transition: 'transform .2s', transform: isOpen ? 'rotate(180deg)' : '' }}>▾</div>
                )}
              </div>

              {isOpen && isAccount && (
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
