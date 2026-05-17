import { useState } from 'react'
import { api, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import { getLevel } from './Profile'

interface Props { me: Me | null; lang: Lang }

const PRESETS_USD = [1, 2, 5, 10, 20, 50]
const FK_CURRENCIES = [
  { code: 'USD', label: '🇺🇸 USD' },
  { code: 'UAH', label: '🇺🇦 UAH' },
  { code: 'RUB', label: '🇷🇺 RUB' },
  { code: 'KZT', label: '🇰🇿 KZT' },
]

type Method = 'fk' | 'crypto'

export default function Balance({ me, lang }: Props) {
  const T = getT(lang)
  const [method, setMethod] = useState<Method>('fk')
  const [selectedUsd, setSelectedUsd] = useState<number | null>(null)
  const [customUsd, setCustomUsd] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

  const usd = me.balance_usd
  const spent = me.total_spent_usd ?? 0
  const lvl = getLevel(spent)

  const hasLocal = (lang === 'ua' && me.rate_uah) || (lang === 'ru' && me.rate_rub)
  const mainBalance = lang === 'ua' && me.rate_uah
    ? `${Math.round(usd * me.rate_uah)}₴`
    : lang === 'ru' && me.rate_rub
    ? `${Math.round(usd * me.rate_rub)}₽`
    : `$${usd.toFixed(2)}`

  const amountUsd = selectedUsd ?? (parseFloat(customUsd) || 0)

  async function handlePay() {
    if (amountUsd < 0.5) return
    setLoading(true)
    setError(null)
    try {
      if (method === 'fk') {
        const { url } = await api.fkCreate(amountUsd, currency)
        window.open(url, '_blank')
      } else {
        const { url } = await api.cryptoCreate(amountUsd)
        window.open(url, '_blank')
      }
    } catch (e: any) {
      setError(e.message ?? 'Error')
    } finally {
      setLoading(false)
    }
  }

  const L = {
    ua: { pay: 'Перейти до оплати', amount: 'Сума ($)', after: 'Баланс зараховується автоматично після оплати' },
    ru: { pay: 'Перейти к оплате', amount: 'Сумма ($)', after: 'Баланс зачисляется автоматически после оплаты' },
    en: { pay: 'Proceed to payment', amount: 'Amount ($)', after: 'Balance is credited automatically after payment' },
  }[lang]

  return (
    <div className="page">
      <h1 style={{ marginBottom: 16 }}>{T.balance}</h1>

      {/* Balance hero */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20, padding: '24px 20px', marginBottom: 10,
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -40, right: -40, width: 180, height: 180,
          borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,107,43,.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 8 }}>
          {T.balance.toUpperCase()}
        </div>
        <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1, marginBottom: 6 }}>
          <span style={{ fontWeight: 800, fontSize: 42 }}>{mainBalance}</span>
        </div>
        {hasLocal && (
          <div style={{ fontSize: 15, color: 'var(--muted)', fontWeight: 400, marginBottom: 16 }}>
            (${usd.toFixed(2)})
          </div>
        )}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: `${lvl.color}15`, border: `1px solid ${lvl.color}30`,
          borderRadius: 20, padding: '6px 14px',
        }}>
          <span style={{ fontSize: 16 }}>{lvl.icon}</span>
          <span style={{ fontWeight: 700, fontSize: 13, color: lvl.color }}>{lvl.name[lang]}</span>
          {lvl.discount > 0 && (
            <span style={{
              fontSize: 11, fontWeight: 700, padding: '1px 7px', borderRadius: 20,
              background: `${lvl.color}25`, color: lvl.color,
            }}>−{lvl.discount}%</span>
          )}
        </div>
      </div>

      {/* Top-up card */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 20, padding: '20px 16px', marginBottom: 10,
      }}>
        {/* Method switcher */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
          {([['fk', '💳', 'Visa / MC'], ['crypto', '💎', 'USDT']] as const).map(([m, icon, label]) => (
            <button key={m} onClick={() => { setMethod(m); setError(null) }} style={{
              flex: 1, padding: '12px 8px', borderRadius: 14, cursor: 'pointer',
              background: method === m ? 'rgba(255,107,43,.15)' : 'var(--card2)',
              border: `1px solid ${method === m ? 'rgba(255,107,43,.45)' : 'var(--border)'}`,
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
            }}>
              <span style={{ fontSize: 22 }}>{icon}</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: method === m ? 'var(--orange)' : 'var(--text2)' }}>
                {label}
              </span>
            </button>
          ))}
        </div>

        {/* FK: currency selector */}
        {method === 'fk' && (
          <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
            {FK_CURRENCIES.map(c => (
              <button key={c.code} onClick={() => setCurrency(c.code)} style={{
                background: currency === c.code ? 'rgba(255,107,43,.15)' : 'var(--card2)',
                border: `1px solid ${currency === c.code ? 'rgba(255,107,43,.4)' : 'var(--border)'}`,
                borderRadius: 10, padding: '6px 12px', cursor: 'pointer',
                fontSize: 12, fontWeight: 700,
                color: currency === c.code ? 'var(--orange)' : 'var(--text2)',
              }}>{c.label}</button>
            ))}
          </div>
        )}

        {/* Crypto: USDT note */}
        {method === 'crypto' && (
          <div style={{
            background: 'rgba(38,161,123,.1)', border: '1px solid rgba(38,161,123,.25)',
            borderRadius: 12, padding: '10px 14px', marginBottom: 12,
            fontSize: 13, color: '#26A17B', fontWeight: 600,
          }}>
            💎 USDT (TON) · @CryptoBot
          </div>
        )}

        {/* Presets */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
          {PRESETS_USD.map(u => {
            const active = selectedUsd === u && !customUsd
            return (
              <button key={u} onClick={() => { setSelectedUsd(u); setCustomUsd(''); setError(null) }} style={{
                background: active ? 'rgba(255,107,43,.15)' : 'var(--card2)',
                border: `1px solid ${active ? 'rgba(255,107,43,.4)' : 'var(--border)'}`,
                borderRadius: 12, padding: '11px 4px', cursor: 'pointer',
                fontWeight: 800, fontSize: 15,
                color: active ? 'var(--orange)' : 'var(--text)',
              }}>${u}</button>
            )
          })}
        </div>

        {/* Custom */}
        <input
          type="number" min="0.5" step="0.5" placeholder={L.amount}
          value={customUsd}
          onChange={e => { setCustomUsd(e.target.value); setSelectedUsd(null); setError(null) }}
          style={{
            width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
            borderRadius: 12, padding: '12px 14px', color: 'var(--text)',
            fontSize: 15, outline: 'none', boxSizing: 'border-box', marginBottom: 12,
          }}
        />

        <button
          className="btn btn-primary"
          disabled={amountUsd < 0.5 || loading}
          onClick={handlePay}
        >
          {loading ? '⏳...' : `${L.pay} $${amountUsd > 0 ? amountUsd.toFixed(2) : '0.00'}`}
        </button>

        {error && (
          <div style={{
            marginTop: 10, padding: '10px 14px', borderRadius: 10, fontSize: 13,
            background: 'rgba(224,80,80,.12)', color: 'var(--red)',
            border: '1px solid rgba(224,80,80,.25)',
          }}>{error}</div>
        )}

        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 10, textAlign: 'center' }}>
          {L.after}
        </div>
      </div>
    </div>
  )
}
