import { useState, useEffect } from 'react'
import { api, type Me, type Order } from '../api'
import { getT, type Lang } from '../i18n'
import LegalFooter from '../components/LegalFooter'

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

  const starsBalance = me.balance_stars
  const usdDisplay = (starsBalance * 0.013).toFixed(2)

  return (
    <div className="page">

      {/* ── Hero card ── */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20,
        padding: '22px 18px 20px',
        marginBottom: 10,
        position: 'relative',
        overflow: 'hidden',
      }}>
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
            background: 'rgba(255,107,43,.2)',
            border: '1.5px solid rgba(255,107,43,.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, fontWeight: 800, color: '#fff', flexShrink: 0,
          }}>
            {me.name.charAt(0).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 17 }}>{me.name}</div>
            {me.username && <div className="muted" style={{ fontSize: 13, marginTop: 1 }}>@{me.username}</div>}
          </div>
        </div>

        {/* Balance */}
        <div>
          <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 6 }}>
            {T.balance.toUpperCase()}
          </div>
          <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1 }}>
            <span style={{ fontWeight: 800, fontSize: 38 }}>⭐{starsBalance}</span>
            <span style={{ fontWeight: 400, fontSize: 18, marginLeft: 10, color: 'var(--muted)' }}>(${usdDisplay})</span>
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
                    )} · ⭐{Math.round(o.price_usd / 0.013)}
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
      <LegalFooter />
    </div>
  )
}
