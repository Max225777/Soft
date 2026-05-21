import { useState } from 'react'
import { api, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import { getLevel } from './Profile'

interface Props { me: Me | null; lang: Lang }

const PRESETS_RUB = [50, 100, 250, 500, 1000]
const PRESETS_USD = [1, 2, 5, 10, 25, 50]

function BottomSheet({ title, subtitle, onClose, children }: {
  title: string; subtitle: string; onClose(): void; children: React.ReactNode
}) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,.75)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
      backdropFilter: 'blur(6px)',
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: 480,
        background: 'linear-gradient(160deg, #1E1428 0%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.25)',
        borderRadius: '24px 24px 0 0',
        padding: '20px 20px 36px',
      }}>
        <div style={{ width: 40, height: 4, borderRadius: 4, background: 'rgba(255,255,255,.15)', margin: '0 auto 20px' }} />
        <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 2 }}>{title}</div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 20 }}>{subtitle}</div>
        {children}
      </div>
    </div>
  )
}

export default function Balance({ me, lang }: Props) {
  const T = getT(lang)
  const [modal, setModal] = useState<'fk' | 'crypto' | null>(null)
  const [fkAmountRub, setFkAmountRub] = useState(0)
  const [customRub, setCustomRub] = useState('')
  const [cryptoAmount, setCryptoAmount] = useState(0)
  const [customUsd, setCustomUsd] = useState('')
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
  const rubRate = me.rate_rub || 90

  const payLabel = lang === 'ru' ? 'Оплатить' : lang === 'ua' ? 'Оплатити' : 'Pay'
  const afterLabel = lang === 'ru' ? 'Баланс зачисляется автоматически' : lang === 'ua' ? 'Баланс зараховується автоматично' : 'Balance credited automatically'
  const cryptoSubtitle = lang === 'ru' ? 'Криптовалюта' : lang === 'ua' ? 'Криптовалюта' : 'Cryptocurrency'

  async function payFK(rub: number) {
    if (rub < 50) return
    setFkLoading(true); setFkError(null)
    try {
      const { url } = await api.fkCreate(rub / rubRate, 'USD')
      window.location.href = url
    } catch (e: any) { setFkError(e.message ?? 'Error') }
    finally { setFkLoading(false) }
  }

  async function payCrypto(amount: number) {
    if (amount < 0.5) return
    setCryptoLoading(true); setCryptoError(null)
    try {
      const { url } = await api.cryptoCreate(amount)
      if (window.Telegram?.WebApp) window.Telegram.WebApp.openLink(url)
      else window.open(url, '_blank')
    } catch (e: any) { setCryptoError(e.message ?? 'Error') }
    finally { setCryptoLoading(false) }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
    borderRadius: 12, padding: '11px 14px', color: 'var(--text)',
    fontSize: 15, outline: 'none', boxSizing: 'border-box',
  }
  const presetBtnStyle = (active: boolean): React.CSSProperties => ({
    background: active ? 'rgba(255,107,43,.15)' : 'var(--card2)',
    border: `1px solid ${active ? 'rgba(255,107,43,.4)' : 'var(--border)'}`,
    borderRadius: 12, padding: '11px 4px', cursor: 'pointer',
    fontWeight: 800, fontSize: 15,
    color: active ? 'var(--orange)' : 'var(--text)',
  })

  return (
    <div className="page">
      <h1 style={{ marginBottom: 16 }}>{T.balance}</h1>

      {/* Balance hero */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20, padding: '24px 20px', marginBottom: 14,
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

      {/* Payment method cards */}
      <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 8, paddingLeft: 4 }}>
        {lang === 'ru' ? 'СПОСОБЫ ПОПОЛНЕНИЯ' : lang === 'ua' ? 'СПОСОБИ ПОПОВНЕННЯ' : 'TOP UP METHODS'}
      </div>

      <button onClick={() => { setFkError(null); setModal('fk') }} style={{
        width: '100%', background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 16, padding: '16px', marginBottom: 8, cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left',
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: 14, flexShrink: 0,
          background: 'rgba(255,107,43,.12)', border: '1px solid rgba(255,107,43,.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24,
        }}>🏦</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 15 }}>СБП / Ру банки</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>🇷🇺 Тільки RU · ~12% комісія</div>
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 18 }}>›</div>
      </button>

      <button onClick={() => { setCryptoError(null); setModal('crypto') }} style={{
        width: '100%',
        background: 'linear-gradient(135deg, rgba(38,161,123,.08), rgba(38,161,123,.03))',
        border: '1px solid rgba(38,161,123,.22)',
        borderRadius: 16, padding: '16px', marginBottom: 8, cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left',
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: 14, flexShrink: 0,
          background: 'rgba(38,161,123,.15)', border: '1px solid rgba(38,161,123,.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24,
        }}>💎</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 15, color: '#26A17B' }}>CryptoBot USDT</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            {cryptoSubtitle} · @CryptoBot · TON
          </div>
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 18 }}>›</div>
      </button>

      {/* FK bottom sheet */}
      {modal === 'fk' && (
        <BottomSheet
          title="🏦 СБП / Ру банки"
          subtitle={lang === 'ru' ? 'Оплата через СБП и банки · комиссия ~12%' : 'Оплата через СБП та банки · комісія ~12%'}
          onClose={() => setModal(null)}
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
            {PRESETS_RUB.map(p => (
              <button key={p} onClick={() => { setFkAmountRub(p); setCustomRub('') }}
                style={presetBtnStyle(fkAmountRub === p && !customRub)}>
                ₽{p}
              </button>
            ))}
          </div>
          <input
            type="number" min="50" step="50"
            placeholder={lang === 'ru' ? 'Своя сумма (₽)' : 'Своя сума (₽)'}
            value={customRub}
            onChange={e => { setCustomRub(e.target.value); setFkAmountRub(parseFloat(e.target.value) || 0) }}
            style={{ ...inputStyle, marginBottom: 12 }}
          />
          {fkError && <div style={{ marginBottom: 10, fontSize: 13, color: 'var(--red)' }}>{fkError}</div>}
          <button className="btn btn-primary" disabled={fkAmountRub < 50 || fkLoading}
            onClick={() => payFK(fkAmountRub)}>
            {fkLoading ? '⏳...' : `${payLabel} ₽${fkAmountRub || 0}`}
          </button>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 10, textAlign: 'center' }}>{afterLabel}</div>
        </BottomSheet>
      )}

      {/* Crypto bottom sheet */}
      {modal === 'crypto' && (
        <BottomSheet
          title="💎 CryptoBot USDT"
          subtitle={`${cryptoSubtitle} · @CryptoBot · TON Network`}
          onClose={() => setModal(null)}
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
            {PRESETS_USD.map(p => (
              <button key={p} onClick={() => { setCryptoAmount(p); setCustomUsd('') }}
                style={presetBtnStyle(cryptoAmount === p && !customUsd)}>
                ${p}
              </button>
            ))}
          </div>
          <input
            type="number" min="0.5" step="0.5"
            placeholder={lang === 'ua' ? 'Сума ($)' : lang === 'ru' ? 'Сумма ($)' : 'Amount ($)'}
            value={customUsd}
            onChange={e => { setCustomUsd(e.target.value); setCryptoAmount(parseFloat(e.target.value) || 0) }}
            style={{ ...inputStyle, marginBottom: 12 }}
          />
          {cryptoError && <div style={{ marginBottom: 10, fontSize: 13, color: 'var(--red)' }}>{cryptoError}</div>}
          <button className="btn btn-primary" disabled={cryptoAmount < 0.5 || cryptoLoading}
            onClick={() => payCrypto(cryptoAmount)}
            style={{ background: 'linear-gradient(135deg, #26A17B, #1a7a5e)' }}>
            {cryptoLoading ? '⏳...' : `${payLabel} $${cryptoAmount > 0 ? cryptoAmount.toFixed(2) : '0.00'} USDT`}
          </button>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 10, textAlign: 'center' }}>{afterLabel}</div>
        </BottomSheet>
      )}
    </div>
  )
}
