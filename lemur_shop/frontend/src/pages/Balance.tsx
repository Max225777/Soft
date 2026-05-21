import { useState } from 'react'
import { api, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import { getLevel } from './Profile'

interface Props { me: Me | null; lang: Lang }

const PRESETS_USD = [1, 2, 5, 10, 25, 50]
const FK_CURRENCIES = [
  { code: 'USD', label: '🇺🇸 USD' },
  { code: 'UAH', label: '🇺🇦 UAH' },
  { code: 'RUB', label: '🇷🇺 RUB' },
  { code: 'KZT', label: '🇰🇿 KZT' },
]

function AmountSelector({ amountUsd, setAmountUsd, lang }: {
  amountUsd: number; setAmountUsd: (v: number) => void; lang: string
}) {
  const [custom, setCustom] = useState('')
  const [sel, setSel] = useState<number | null>(null)
  const L = lang === 'ua' ? 'Сума ($)' : lang === 'ru' ? 'Сумма ($)' : 'Amount ($)'
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
        {PRESETS_USD.map(u => {
          const active = sel === u && !custom
          return (
            <button key={u} onClick={() => { setSel(u); setCustom(''); setAmountUsd(u) }} style={{
              background: active ? 'rgba(255,107,43,.15)' : 'var(--card2)',
              border: `1px solid ${active ? 'rgba(255,107,43,.4)' : 'var(--border)'}`,
              borderRadius: 12, padding: '11px 4px', cursor: 'pointer',
              fontWeight: 800, fontSize: 15, color: active ? 'var(--orange)' : 'var(--text)',
            }}>${u}</button>
          )
        })}
      </div>
      <input
        type="number" min="0.5" step="0.5" placeholder={L}
        value={custom}
        onChange={e => { setCustom(e.target.value); setSel(null); setAmountUsd(parseFloat(e.target.value) || 0) }}
        style={{
          width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
          borderRadius: 12, padding: '11px 14px', color: 'var(--text)',
          fontSize: 15, outline: 'none', boxSizing: 'border-box',
        }}
      />
    </>
  )
}

export default function Balance({ me, lang }: Props) {
  const T = getT(lang)
  const [fkAmount, setFkAmount] = useState(0)
  const [cryptoAmount, setCryptoAmount] = useState(0)
  const [fkLoading, setFkLoading] = useState(false)
  const [cryptoLoading, setCryptoLoading] = useState(false)
  const [fkError, setFkError] = useState<string | null>(null)
  const [cryptoError, setCryptoError] = useState<string | null>(null)

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

  const L = {
    ua: { pay: 'Перейти до оплати', after: 'Баланс зараховується автоматично' },
    ru: { pay: 'Перейти к оплате', after: 'Баланс зачисляется автоматически' },
    en: { pay: 'Proceed to payment', after: 'Balance credited automatically' },
  }[lang]

  async function payFK() {
    if (fkAmount < 0.5) return
    setFkLoading(true); setFkError(null)
    try {
      const { url } = await api.fkCreate(fkAmount, 'USD')
      if (window.Telegram?.WebApp) window.Telegram.WebApp.openLink(url)
      else window.open(url, '_blank')
    } catch (e: any) { setFkError(e.message ?? 'Error') }
    finally { setFkLoading(false) }
  }

  async function payCrypto() {
    if (cryptoAmount < 0.5) return
    setCryptoLoading(true); setCryptoError(null)
    try {
      const { url } = await api.cryptoCreate(cryptoAmount)
      if (window.Telegram?.WebApp) window.Telegram.WebApp.openLink(url)
      else window.open(url, '_blank')
    } catch (e: any) { setCryptoError(e.message ?? 'Error') }
    finally { setCryptoLoading(false) }
  }

  return (
    <div className="page">
      <h1 style={{ marginBottom: 16 }}>{T.balance} <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 400 }}>v2</span></h1>

      {/* Balance hero */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20, padding: '24px 20px', marginBottom: 10,
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -40, right: -40, width: 180, height: 180, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,107,43,.12) 0%, transparent 70%)', pointerEvents: 'none',
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
            <span style={{ fontSize: 11, fontWeight: 700, padding: '1px 7px', borderRadius: 20, background: `${lvl.color}25`, color: lvl.color }}>
              −{lvl.discount}%
            </span>
          )}
        </div>
      </div>

      {/* FreеKassa */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 20, padding: '18px 16px', marginBottom: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <span style={{ fontSize: 26 }}>💳</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 15 }}>
              {lang === 'ua' ? 'Оплата карткою' : lang === 'ru' ? 'Оплата картой' : 'Card payment'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>Visa / Mastercard · 🇷🇺 RU</div>
          </div>
        </div>
        {lang === 'ua' && (
          <div style={{ fontSize: 12, color: 'var(--muted)', background: 'var(--card2)', borderRadius: 10, padding: '8px 12px', marginBottom: 12 }}>
            ⚠️ Доступно тільки для RU карток. Для UA — використовуй USDT нижче.
          </div>
        )}

        <div style={{ marginBottom: 12 }}>
          <AmountSelector amountUsd={fkAmount} setAmountUsd={setFkAmount} lang={lang} />
        </div>

        <button className="btn btn-primary" disabled={fkAmount < 0.5 || fkLoading} onClick={payFK}>
          {fkLoading ? '⏳...' : `${L.pay} $${fkAmount > 0 ? fkAmount.toFixed(2) : '0.00'}`}
        </button>
        {fkError && <div style={{ marginTop: 8, fontSize: 13, color: 'var(--red)' }}>{fkError}</div>}
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>{L.after}</div>
      </div>

      {/* CryptoBot */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(38,161,123,.08), rgba(38,161,123,.03))',
        border: '1px solid rgba(38,161,123,.22)',
        borderRadius: 20, padding: '18px 16px', marginBottom: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <span style={{ fontSize: 26 }}>💎</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 15, color: '#26A17B' }}>USDT</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>@CryptoBot · TON Network</div>
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <AmountSelector amountUsd={cryptoAmount} setAmountUsd={setCryptoAmount} lang={lang} />
        </div>

        <button
          className="btn btn-primary"
          disabled={cryptoAmount < 0.5 || cryptoLoading}
          onClick={payCrypto}
          style={{ background: 'linear-gradient(135deg, #26A17B, #1a7a5e)' }}
        >
          {cryptoLoading ? '⏳...' : `${L.pay} $${cryptoAmount > 0 ? cryptoAmount.toFixed(2) : '0.00'} USDT`}
        </button>
        {cryptoError && <div style={{ marginTop: 8, fontSize: 13, color: 'var(--red)' }}>{cryptoError}</div>}
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>{L.after}</div>
      </div>
    </div>
  )
}
