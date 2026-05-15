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

export default function Profile({ me, lang, onChangeLang }: Props) {
  const T = getT(lang)
  const [orders, setOrders] = useState<Order[]>([])
  const [loadingOrders, setLoadingOrders] = useState(true)
  const [openOrder, setOpenOrder] = useState<number | null>(null)
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

  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

  const usd = me.balance_usd
  const balanceLocal = lang === 'ua' && me.rate_uah
    ? ` (~${Math.round(usd * me.rate_uah)}₴)`
    : lang === 'ru' && me.rate_rub
    ? ` (~${Math.round(usd * me.rate_rub)}₽)`
    : ''

  return (
    <div className="page">
      {/* Balance */}
      <div className="card" style={{ textAlign: 'center', marginBottom: 12 }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{T.balance}</div>
        <div style={{ fontWeight: 700, fontSize: 28, color: 'var(--orange)' }}>
          ${usd.toFixed(2)}{balanceLocal}
        </div>
      </div>

      {/* User info */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12 }}>
        <div style={{
          width: 52, height: 52, borderRadius: '50%',
          background: 'var(--orange)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22, fontWeight: 700, flexShrink: 0,
        }}>
          {me.name.charAt(0).toUpperCase()}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 16 }}>{me.name}</div>
          {me.username && <div className="muted" style={{ fontSize: 13 }}>@{me.username}</div>}
        </div>
        <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--brown2)' }}>
          {me.orders_count} {T.orders.toLowerCase()}
        </div>
      </div>

      {/* Language change */}
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{T.change_lang}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['ru', 'ua', 'en'] as Lang[]).map(l => (
            <button
              key={l}
              className={`btn ${lang === l ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, padding: '8px 4px', fontSize: 13 }}
              onClick={() => changeLang(l)}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
      </div>

      {/* My accounts */}
      <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 10 }}>{T.my_accounts}</div>

      {loadingOrders ? (
        <>
          <div className="card"><div className="skeleton" style={{ height: 48 }} /></div>
          <div className="card"><div className="skeleton" style={{ height: 48 }} /></div>
        </>
      ) : orders.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--brown2)' }}>{T.no_orders}</div>
      ) : (
        orders.map(o => {
          const [phone, code] = o.delivered_data ? o.delivered_data.split('\n') : ['', '']
          const isOpen = openOrder === o.id
          return (
            <div key={o.id} className="card" style={{ marginBottom: 8 }}>
              <div
                style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
                onClick={() => setOpenOrder(isOpen ? null : o.id)}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>
                    {T.order_num} #{String(o.id).padStart(5, '0')}
                  </div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {new Date(o.created_at).toLocaleDateString()} · ${o.price_usd.toFixed(2)}
                  </div>
                </div>
                <div style={{ fontSize: 18 }}>{isOpen ? '▲' : '▼'}</div>
              </div>

              {isOpen && phone && (
                <div style={{ marginTop: 12, borderTop: '1px solid var(--sand)', paddingTop: 12 }}>
                  <div style={{ marginBottom: 8 }}>
                    <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>📱 {T.your_phone}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <code style={{ flex: 1, fontSize: 15, fontWeight: 700 }}>{phone}</code>
                      <button className="btn btn-secondary" style={{ width: 'auto', padding: '5px 10px', fontSize: 12 }}
                        onClick={() => copy(phone, `phone-${o.id}`)}>
                        {copied === `phone-${o.id}` ? T.copied : T.copy}
                      </button>
                    </div>
                  </div>
                  {code && (
                    <div>
                      <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>🔑 {T.your_code}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <code style={{ flex: 1, fontSize: 17, fontWeight: 700, letterSpacing: 2 }}>{code}</code>
                        <button className="btn btn-secondary" style={{ width: 'auto', padding: '5px 10px', fontSize: 12 }}
                          onClick={() => copy(code, `code-${o.id}`)}>
                          {copied === `code-${o.id}` ? T.copied : T.copy}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })
      )}

      {me.is_admin && (
        <div className="card" style={{ background: 'var(--sand)', textAlign: 'center', marginTop: 8 }}>
          <span>⚙️ Admin</span>
        </div>
      )}
    </div>
  )
}
