import { useState, useEffect } from 'react'
import { api, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import { getLevel } from './Profile'

interface Props { me: Me | null; lang: Lang; onRefresh?: () => void }

const PRESETS_USD = [1, 2, 5, 10, 20, 50]

export default function Balance({ me, lang, onRefresh }: Props) {
  const T = getT(lang)
  const [starsPerUsd, setStarsPerUsd] = useState<number>(120)
  const [selectedUsd, setSelectedUsd] = useState<number | null>(null)
  const [customUsd, setCustomUsd] = useState('')
  const [paying, setPaying] = useState(false)
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)

  useEffect(() => {
    api.starsRate().then(r => setStarsPerUsd(r.stars_per_usd)).catch(() => {})
  }, [])

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
  const starsNeeded = amountUsd > 0 ? Math.round(amountUsd * starsPerUsd) : 0

  const localStr = (u: number) => {
    if (lang === 'ua' && me.rate_uah) return `${Math.round(u * me.rate_uah)}₴`
    if (lang === 'ru' && me.rate_rub) return `${Math.round(u * me.rate_rub)}₽`
    return `$${u.toFixed(2)}`
  }

  async function handlePay() {
    if (amountUsd < 0.5) return
    setPaying(true)
    setMsg(null)
    try {
      const { invoice_url } = await api.starsInvoice(amountUsd)
      window.Telegram?.WebApp?.openInvoice(invoice_url, (status) => {
        setPaying(false)
        if (status === 'paid') {
          setMsg({ text: T.stars_success, ok: true })
          setSelectedUsd(null)
          setCustomUsd('')
          onRefresh?.()
        } else if (status === 'cancelled' || status === 'failed') {
          setMsg({ text: T.stars_failed, ok: false })
        }
      })
    } catch (e: any) {
      setPaying(false)
      setMsg({ text: e.message ?? T.stars_failed, ok: false })
    }
  }

  return (
    <div className="page">
      <h1 style={{ marginBottom: 16 }}>{T.balance}</h1>

      {/* Balance hero */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20,
        padding: '24px 20px',
        marginBottom: 10,
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -40, right: -40,
          width: 180, height: 180, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,107,43,.12) 0%, transparent 70%)',
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

      {/* Stars top-up */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(255,184,48,.08), rgba(255,184,48,.03))',
        border: '1px solid rgba(255,184,48,.22)',
        borderRadius: 20, padding: '20px 16px', marginBottom: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <span style={{ fontSize: 24 }}>⭐</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--gold)' }}>{T.stars_topup}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              1 ⭐ = ${(1 / starsPerUsd).toFixed(3)}
            </div>
          </div>
        </div>

        {/* Preset amounts */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
          {PRESETS_USD.map(u => {
            const active = selectedUsd === u && !customUsd
            return (
              <button
                key={u}
                onClick={() => { setSelectedUsd(u); setCustomUsd(''); setMsg(null) }}
                style={{
                  background: active ? 'rgba(255,184,48,.2)' : 'var(--card2)',
                  border: `1px solid ${active ? 'rgba(255,184,48,.5)' : 'var(--border)'}`,
                  borderRadius: 12, padding: '10px 4px',
                  cursor: 'pointer', transition: 'all .15s',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                }}
              >
                <span style={{ fontWeight: 800, fontSize: 15, color: active ? 'var(--gold)' : 'var(--text)' }}>
                  {localStr(u)}
                </span>
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                  {Math.round(u * starsPerUsd)} ⭐
                </span>
              </button>
            )
          })}
        </div>

        {/* Custom amount */}
        <div style={{ marginBottom: 14 }}>
          <input
            type="number"
            min="0.5"
            step="0.5"
            placeholder={lang === 'ua' ? 'Своя сума ($)' : lang === 'ru' ? 'Своя сумма ($)' : 'Custom ($)'}
            value={customUsd}
            onChange={e => { setCustomUsd(e.target.value); setSelectedUsd(null); setMsg(null) }}
            style={{
              width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
              borderRadius: 12, padding: '12px 14px', color: 'var(--text)',
              fontSize: 15, outline: 'none', boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Preview */}
        {starsNeeded > 0 && (
          <div style={{
            background: 'rgba(255,184,48,.08)', border: '1px solid rgba(255,184,48,.18)',
            borderRadius: 12, padding: '12px 14px', marginBottom: 14,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ color: 'var(--muted)', fontSize: 14 }}>
              {lang === 'ua' ? 'Зарахується' : lang === 'ru' ? 'Зачислится' : 'You get'}
            </span>
            <span style={{ fontWeight: 800, fontSize: 16, color: 'var(--gold)' }}>
              {localStr(amountUsd)}
            </span>
          </div>
        )}

        {/* Pay button */}
        <button
          className="btn btn-primary"
          disabled={starsNeeded < 1 || paying}
          onClick={handlePay}
          style={{ background: 'linear-gradient(135deg, #FFB830, #FF8C00)' }}
        >
          {paying ? T.stars_processing : starsNeeded > 0 ? T.stars_pay(starsNeeded) : T.stars_topup}
        </button>

        {msg && (
          <div style={{
            marginTop: 10, padding: '10px 14px', borderRadius: 10, fontSize: 14, fontWeight: 600,
            background: msg.ok ? 'rgba(76,175,114,.12)' : 'rgba(224,80,80,.12)',
            color: msg.ok ? 'var(--green)' : 'var(--red)',
            border: `1px solid ${msg.ok ? 'rgba(76,175,114,.25)' : 'rgba(224,80,80,.25)'}`,
          }}>
            {msg.text}
          </div>
        )}
      </div>

      {/* Support top-up */}
      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>💳 {T.topup}</div>
        <div className="muted" style={{ fontSize: 13 }}>{T.topup_info}</div>
      </div>
    </div>
  )
}
