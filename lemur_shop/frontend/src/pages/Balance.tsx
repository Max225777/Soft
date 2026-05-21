import { useState } from 'react'
import { api, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import { getLevel } from './Profile'
import LegalFooter from '../components/LegalFooter'

interface Props { me: Me | null; lang: Lang }

const PRESETS_RUB = [100, 250, 500, 1000]
const PRESETS_USD = [1, 2, 5, 10, 25, 50]
const PRESETS_STARS_USD = [1, 2, 5, 10, 25]

const SLIDE_STYLE = `
  @keyframes expand-down {
    from { opacity: 0; transform: translateY(-12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`

function ExpandPanel({ children }: { children: React.ReactNode }) {
  return (
    <>
      <style>{SLIDE_STYLE}</style>
      <div style={{
        animation: 'expand-down .25s cubic-bezier(.32,1,.6,1)',
        borderTop: '1px solid var(--border)',
        padding: '14px 16px 16px',
      }}>
        {children}
      </div>
    </>
  )
}

export default function Balance({ me, lang }: Props) {
  const T = getT(lang)
  const [open, setOpen] = useState<'fk' | 'crypto' | 'stars' | null>(null)
  const [fkAmount, setFkAmount] = useState(0)
  const [customRub, setCustomRub] = useState('')
  const [cryptoAmount, setCryptoAmount] = useState(0)
  const [customUsd, setCustomUsd] = useState('')
  const [starsAmount, setStarsAmount] = useState(0)
  const [customStars, setCustomStars] = useState('')
  const [fkLoading, setFkLoading] = useState(false)
  const [cryptoLoading, setCryptoLoading] = useState(false)
  const [starsLoading, setStarsLoading] = useState(false)
  const [fkError, setFkError] = useState<string | null>(null)
  const [cryptoError, setCryptoError] = useState<string | null>(null)
  const [starsError, setStarsError] = useState<string | null>(null)

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

  const payLabel = lang === 'ru' ? 'Пополнить' : lang === 'ua' ? 'Поповнити' : 'Pay'
  const afterLabel = lang === 'ru' ? 'Баланс зачисляется автоматически' : lang === 'ua' ? 'Баланс зараховується автоматично' : 'Balance credited automatically'

  async function payFK(rub: number) {
    if (rub < 100) return
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

  async function payStars(usd: number) {
    if (usd < 0.5) return
    setStarsLoading(true); setStarsError(null)
    try {
      const { invoice_url, stars } = await api.starsInvoice(usd)
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.openInvoice(invoice_url, status => {
          if (status === 'paid') {
            setStarsError(null)
            setOpen(null)
          } else if (status === 'cancelled' || status === 'failed') {
            setStarsError(T.stars_failed)
          }
        })
      } else {
        window.open(invoice_url, '_blank')
      }
    } catch (e: any) { setStarsError(e.message ?? 'Error') }
    finally { setStarsLoading(false) }
  }

  function toggleFK() {
    if (open === 'fk') { setOpen(null); return }
    setFkError(null); setFkAmount(0); setCustomRub(''); setOpen('fk')
  }
  function toggleCrypto() {
    if (open === 'crypto') { setOpen(null); return }
    setCryptoError(null); setCryptoAmount(0); setCustomUsd(''); setOpen('crypto')
  }
  function toggleStars() {
    if (open === 'stars') { setOpen(null); return }
    setStarsError(null); setStarsAmount(0); setCustomStars(''); setOpen('stars')
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
    borderRadius: 12, padding: '11px 14px', color: 'var(--text)',
    fontSize: 15, outline: 'none', boxSizing: 'border-box',
  }

  const presetBtn = (active: boolean): React.CSSProperties => ({
    background: active ? 'rgba(255,107,43,.15)' : 'var(--card2)',
    border: `1px solid ${active ? 'rgba(255,107,43,.4)' : 'var(--border)'}`,
    borderRadius: 12, padding: '11px 4px', cursor: 'pointer',
    fontWeight: 800, fontSize: 15,
    color: active ? 'var(--orange)' : 'var(--text)',
    width: '100%',
  })

  return (
    <div className="page">
      <h1 style={{ marginBottom: 16 }}>{T.balance}</h1>

      {/* Balance hero */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20, padding: '20px 18px', marginBottom: 14,
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -40, right: -40, width: 180, height: 180, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,107,43,.12) 0%, transparent 70%)', pointerEvents: 'none',
        }} />
        <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 6 }}>
          {T.balance.toUpperCase()}
        </div>
        <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1, marginBottom: hasLocal ? 4 : 12 }}>
          <span style={{ fontWeight: 800, fontSize: 40 }}>{mainBalance}</span>
        </div>
        {hasLocal && (
          <div style={{ fontSize: 14, color: 'var(--muted)', marginBottom: 12 }}>(${usd.toFixed(2)})</div>
        )}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: `${lvl.color}15`, border: `1px solid ${lvl.color}30`,
          borderRadius: 20, padding: '5px 12px',
        }}>
          <span style={{ fontSize: 15 }}>{lvl.icon}</span>
          <span style={{ fontWeight: 700, fontSize: 13, color: lvl.color }}>{lvl.name[lang]}</span>
          {lvl.discount > 0 && (
            <span style={{ fontSize: 11, fontWeight: 700, padding: '1px 7px', borderRadius: 20, background: `${lvl.color}25`, color: lvl.color }}>
              −{lvl.discount}%
            </span>
          )}
        </div>
      </div>

      {/* Section label */}
      <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 8, paddingLeft: 4 }}>
        {lang === 'ru' ? 'СПОСОБЫ ПОПОЛНЕНИЯ' : lang === 'ua' ? 'СПОСОБИ ПОПОВНЕННЯ' : 'TOP UP METHODS'}
      </div>

      {/* FK card */}
      <div className="card" style={{ marginBottom: 8, padding: 0, overflow: 'hidden' }}>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', cursor: 'pointer' }}
          onClick={toggleFK}
        >
          <div style={{
            width: 38, height: 38, borderRadius: 11, flexShrink: 0,
            background: 'rgba(255,107,43,.12)', border: '1px solid rgba(255,107,43,.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
          }}>🏦</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>СБП / Ру банки</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>🇷🇺 Тільки RU · ~12% комісія</div>
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 18, transition: 'transform .2s', transform: open === 'fk' ? 'rotate(90deg)' : '' }}>›</div>
        </div>

        {open === 'fk' && (
          <ExpandPanel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 10 }}>
              {PRESETS_RUB.map(p => (
                <button key={p} onClick={() => { setFkAmount(p); setCustomRub('') }}
                  style={presetBtn(fkAmount === p && !customRub)}>
                  ₽{p}
                </button>
              ))}
            </div>
            <input
              type="number" min="100" step="50"
              placeholder={lang === 'ru' ? 'Своя сумма (₽)' : 'Своя сума (₽)'}
              value={customRub}
              onChange={e => { setCustomRub(e.target.value); setFkAmount(parseFloat(e.target.value) || 0) }}
              style={{ ...inputStyle, marginBottom: 10 }}
            />
            {fkAmount > 0 && fkAmount < 100 && (
              <div style={{ marginBottom: 8, fontSize: 12, color: 'var(--red)' }}>
                {lang === 'ru' ? 'Минимальная сумма пополнения: ₽100' : 'Мінімальна сума поповнення: ₽100'}
              </div>
            )}
            {fkError && <div style={{ marginBottom: 8, fontSize: 13, color: 'var(--red)' }}>{fkError}</div>}
            <button className="btn btn-primary" disabled={fkAmount < 100 || fkLoading}
              style={fkAmount < 100 ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
              onClick={() => payFK(fkAmount)}>
              {fkLoading ? '⏳...' : fkAmount >= 100 ? `${payLabel} ₽${fkAmount}` : `${payLabel} (мін. ₽100)`}
            </button>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>{afterLabel}</div>
          </ExpandPanel>
        )}
      </div>

      {/* Crypto card */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(38,161,123,.08), rgba(38,161,123,.03))',
        border: '1px solid rgba(38,161,123,.22)',
        borderRadius: 14, marginBottom: 8, overflow: 'hidden',
      }}>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', cursor: 'pointer' }}
          onClick={toggleCrypto}
        >
          <div style={{
            width: 38, height: 38, borderRadius: 11, flexShrink: 0,
            background: 'rgba(38,161,123,.15)', border: '1px solid rgba(38,161,123,.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
          }}>💎</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15, color: '#26A17B' }}>CryptoBot USDT</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              {lang === 'ru' ? 'Криптовалюта' : lang === 'ua' ? 'Криптовалюта' : 'Cryptocurrency'} · @CryptoBot · TON
            </div>
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 18, transition: 'transform .2s', transform: open === 'crypto' ? 'rotate(90deg)' : '' }}>›</div>
        </div>

        {open === 'crypto' && (
          <ExpandPanel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
              {PRESETS_USD.map(p => (
                <button key={p} onClick={() => { setCryptoAmount(p); setCustomUsd('') }}
                  style={presetBtn(cryptoAmount === p && !customUsd)}>
                  ${p}
                </button>
              ))}
            </div>
            <input
              type="number" min="0.5" step="0.5"
              placeholder={lang === 'ua' ? 'Сума ($)' : lang === 'ru' ? 'Сумма ($)' : 'Amount ($)'}
              value={customUsd}
              onChange={e => { setCustomUsd(e.target.value); setCryptoAmount(parseFloat(e.target.value) || 0) }}
              style={{ ...inputStyle, marginBottom: 10 }}
            />
            {cryptoError && <div style={{ marginBottom: 8, fontSize: 13, color: 'var(--red)' }}>{cryptoError}</div>}
            <button className="btn btn-primary" disabled={cryptoAmount < 0.5 || cryptoLoading}
              onClick={() => payCrypto(cryptoAmount)}
              style={{ background: 'linear-gradient(135deg, #26A17B, #1a7a5e)' }}>
              {cryptoLoading ? '⏳...' : `${payLabel} $${cryptoAmount > 0 ? cryptoAmount.toFixed(2) : '0.00'} USDT`}
            </button>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>{afterLabel}</div>
          </ExpandPanel>
        )}
      </div>
      {/* Stars card */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(255,184,48,.08), rgba(255,184,48,.03))',
        border: '1px solid rgba(255,184,48,.22)',
        borderRadius: 14, marginBottom: 8, overflow: 'hidden',
      }}>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', cursor: 'pointer' }}
          onClick={toggleStars}
        >
          <div style={{
            width: 38, height: 38, borderRadius: 11, flexShrink: 0,
            background: 'rgba(255,184,48,.15)', border: '1px solid rgba(255,184,48,.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
          }}>⭐</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15, color: '#FFB830' }}>Telegram Stars</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              {lang === 'ru' ? 'Оплата звёздами Telegram' : lang === 'ua' ? 'Оплата зірками Telegram' : 'Pay with Telegram Stars'}
            </div>
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 18, transition: 'transform .2s', transform: open === 'stars' ? 'rotate(90deg)' : '' }}>›</div>
        </div>

        {open === 'stars' && (
          <ExpandPanel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginBottom: 10 }}>
              {PRESETS_STARS_USD.map(p => (
                <button key={p} onClick={() => { setStarsAmount(p); setCustomStars('') }}
                  style={presetBtn(starsAmount === p && !customStars)}>
                  ${p}
                </button>
              ))}
            </div>
            <input
              type="number" min="0.5" step="0.5"
              placeholder={lang === 'ru' ? 'Сумма ($)' : lang === 'ua' ? 'Сума ($)' : 'Amount ($)'}
              value={customStars}
              onChange={e => { setCustomStars(e.target.value); setStarsAmount(parseFloat(e.target.value) || 0) }}
              style={{ ...inputStyle, marginBottom: 10 }}
            />
            {starsError && <div style={{ marginBottom: 8, fontSize: 13, color: 'var(--red)' }}>{starsError}</div>}
            <button className="btn btn-primary" disabled={starsAmount < 0.5 || starsLoading}
              onClick={() => payStars(starsAmount)}
              style={{ background: 'linear-gradient(135deg, #FFB830, #e09000)' }}>
              {starsLoading ? '⏳...' : `${payLabel} $${starsAmount > 0 ? starsAmount.toFixed(2) : '0.00'} ⭐`}
            </button>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>
              {lang === 'ru' ? 'Оплата через Telegram Stars' : lang === 'ua' ? 'Оплата через Telegram Stars' : 'Pay via Telegram Stars'}
            </div>
          </ExpandPanel>
        )}
      </div>

      <LegalFooter />
    </div>
  )
}
