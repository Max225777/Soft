import { useState } from 'react'
import { api, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import { getLevel } from './Profile'

interface Props { me: Me | null; lang: Lang }

const PRESETS_RUB = [50, 100, 250, 500, 1000]

function UsdAmountSelector({ amount, setAmount, lang }: {
  amount: number; setAmount: (v: number) => void; lang: string
}) {
  const [custom, setCustom] = useState('')
  const [sel, setSel] = useState<number | null>(null)
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
        {[1, 2, 5, 10, 25, 50].map(p => {
          const active = sel === p && !custom
          return (
            <button key={p} onClick={() => { setSel(p); setCustom(''); setAmount(p) }} style={{
              background: active ? 'rgba(255,107,43,.15)' : 'var(--card2)',
              border: `1px solid ${active ? 'rgba(255,107,43,.4)' : 'var(--border)'}`,
              borderRadius: 12, padding: '11px 4px', cursor: 'pointer',
              fontWeight: 800, fontSize: 15, color: active ? 'var(--orange)' : 'var(--text)',
            }}>${p}</button>
          )
        })}
      </div>
      <input
        type="number" min="0.5" step="0.5"
        placeholder={lang === 'ua' ? 'Сума ($)' : lang === 'ru' ? 'Сумма ($)' : 'Amount ($)'}
        value={custom}
        onChange={e => { setCustom(e.target.value); setSel(null); setAmount(parseFloat(e.target.value) || 0) }}
        style={{
          width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
          borderRadius: 12, padding: '11px 14px', color: 'var(--text)',
          fontSize: 15, outline: 'none', boxSizing: 'border-box',
        }}
      />
    </>
  )
}

function FKModal({ amountRub, rubRate, lang, onConfirm, onCancel, loading, error }: {
  amountRub: number; rubRate: number; lang: Lang
  onConfirm(): void; onCancel(): void; loading: boolean; error: string | null
}) {
  const payLabel = lang === 'ru' ? 'Оплатить' : lang === 'ua' ? 'Оплатити' : 'Pay'
  const cancelLabel = lang === 'ru' ? 'Отмена' : lang === 'ua' ? 'Скасувати' : 'Cancel'
  const afterLabel = lang === 'ru' ? 'Баланс зачисляется автоматически' : lang === 'ua' ? 'Баланс зараховується автоматично' : 'Balance credited automatically'

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,.75)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
      backdropFilter: 'blur(6px)',
    }} onClick={onCancel}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: 480,
        background: 'linear-gradient(160deg, #1E1428 0%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.25)',
        borderRadius: '24px 24px 0 0',
        padding: '20px 20px 32px',
      }}>
        <div style={{ width: 40, height: 4, borderRadius: 4, background: 'rgba(255,255,255,.15)', margin: '0 auto 20px' }} />

        <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 4 }}>
          🏦 СБП / Ру банки
        </div>
        <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 18 }}>
          {lang === 'ru' ? 'Пополнение через СБП · комиссия ~12%' : 'Поповнення через СБП · комісія ~12%'}
        </div>

        <div style={{
          background: 'rgba(255,255,255,.04)', border: '1px solid var(--border)',
          borderRadius: 14, padding: '16px', marginBottom: 20,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
              {lang === 'ru' ? 'Сумма оплаты' : 'Сума оплати'}
            </div>
            <div style={{ fontWeight: 800, fontSize: 28, color: 'var(--orange)' }}>₽{amountRub}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 4 }}>
              {lang === 'ru' ? 'Зачислится' : 'Зарахується'}
            </div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>
              ~${(amountRub * 0.88 / rubRate).toFixed(2)}
            </div>
          </div>
        </div>

        {error && <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--red)' }}>{error}</div>}

        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" style={{ flex: 1 }} onClick={onCancel}>{cancelLabel}</button>
          <button className="btn btn-primary" style={{ flex: 2 }} disabled={loading} onClick={onConfirm}>
            {loading ? '⏳...' : `${payLabel} ₽${amountRub}`}
          </button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 12, textAlign: 'center' }}>{afterLabel}</div>
      </div>
    </div>
  )
}

export default function Balance({ me, lang }: Props) {
  const T = getT(lang)
  const [fkModal, setFkModal] = useState<number | null>(null)
  const [customRub, setCustomRub] = useState('')
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

  const rubRate = me.rate_rub || 90

  async function payFK(amountRub: number) {
    setFkLoading(true); setFkError(null)
    try {
      const { url } = await api.fkCreate(amountRub / rubRate, 'USD')
      window.location.href = url
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

  const afterLabel = lang === 'ru' ? 'Баланс зачисляется автоматически' : lang === 'ua' ? 'Баланс зараховується автоматично' : 'Balance credited automatically'

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

      {/* СБП / Ру банки */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 20, padding: '18px 16px', marginBottom: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <span style={{ fontSize: 26 }}>🏦</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 15 }}>СБП / Ру банки</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>🇷🇺 Тільки для RU · ~12% комісія</div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 10 }}>
          {PRESETS_RUB.map(rub => (
            <button key={rub} onClick={() => { setFkError(null); setFkModal(rub) }} style={{
              background: 'var(--card2)', border: '1px solid var(--border)',
              borderRadius: 14, padding: '16px 8px', cursor: 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
              transition: 'border-color .15s',
            }}>
              <span style={{ fontWeight: 800, fontSize: 22, color: 'var(--text)' }}>₽{rub}</span>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                {lang === 'ru' ? 'Пополнить' : 'Поповнити'}
              </span>
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="number" min="50" step="50"
            placeholder={lang === 'ru' ? 'Своя сумма (₽)' : 'Своя сума (₽)'}
            value={customRub}
            onChange={e => setCustomRub(e.target.value)}
            style={{
              flex: 1, background: 'var(--card2)', border: '1px solid var(--border)',
              borderRadius: 12, padding: '11px 14px', color: 'var(--text)',
              fontSize: 15, outline: 'none',
            }}
          />
          <button
            className="btn btn-primary"
            disabled={!customRub || parseFloat(customRub) < 50}
            onClick={() => { setFkError(null); setFkModal(parseFloat(customRub)) }}
            style={{ flexShrink: 0, padding: '11px 16px', fontSize: 14 }}
          >
            {lang === 'ru' ? 'Далее' : 'Далі'} →
          </button>
        </div>
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
          <UsdAmountSelector amount={cryptoAmount} setAmount={setCryptoAmount} lang={lang} />
        </div>

        <button
          className="btn btn-primary"
          disabled={cryptoAmount < 0.5 || cryptoLoading}
          onClick={payCrypto}
          style={{ background: 'linear-gradient(135deg, #26A17B, #1a7a5e)' }}
        >
          {cryptoLoading ? '⏳...' : `${lang === 'ru' ? 'Оплатить' : lang === 'ua' ? 'Оплатити' : 'Pay'} $${cryptoAmount > 0 ? cryptoAmount.toFixed(2) : '0.00'} USDT`}
        </button>
        {cryptoError && <div style={{ marginTop: 8, fontSize: 13, color: 'var(--red)' }}>{cryptoError}</div>}
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>{afterLabel}</div>
      </div>

      {fkModal !== null && (
        <FKModal
          amountRub={fkModal}
          rubRate={rubRate}
          lang={lang}
          loading={fkLoading}
          error={fkError}
          onCancel={() => { setFkModal(null); setFkError(null) }}
          onConfirm={() => payFK(fkModal)}
        />
      )}
    </div>
  )
}
