import { useState } from 'react'
import { api, type Me } from '../api'
import { getT, type Lang } from '../i18n'
import LegalFooter from '../components/LegalFooter'
import BioPromoButton from '../components/BioPromoButton'

interface Props { me: Me | null; lang: Lang; balanceDiff?: number | null }

const PRESETS_USD = [1, 2, 5, 10, 25, 50]
const PRESETS_STARS = [1, 5, 10, 50, 100]
const STARS_PER_USD = 141

const SLIDE_STYLE = `
  @keyframes expand-down {
    from { opacity: 0; transform: translateY(-12px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes topup-pop {
    0%   { opacity: 0; transform: translateX(-50%) translateY(-16px) scale(.92); }
    55%  { transform: translateX(-50%) translateY(4px) scale(1.02); }
    100% { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
  }
  @keyframes star-spin {
    0%   { transform: rotate(0deg) scale(1); }
    50%  { transform: rotate(20deg) scale(1.3); }
    100% { transform: rotate(0deg) scale(1); }
  }
  @keyframes balance-plus {
    0%   { opacity: 0; transform: translateY(0); }
    20%  { opacity: 1; }
    80%  { opacity: 1; }
    100% { opacity: 0; transform: translateY(-32px); }
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

export default function Balance({ me, lang, balanceDiff }: Props) {
  const T = getT(lang)
  const [open, setOpen] = useState<'crypto' | 'heleket' | 'stars' | null>(null)
  const [promoCode, setPromoCode] = useState('')
  const [promoLoading, setPromoLoading] = useState(false)
  const [promoResult, setPromoResult] = useState<{ ok: boolean; stars?: number; error?: string } | null>(null)
  const [cryptoAmount, setCryptoAmount] = useState(0)
  const [customUsd, setCustomUsd] = useState('')
  const [starsCount, setStarsCount] = useState(0)
  const [customStars, setCustomStars] = useState('')
  const [cryptoLoading, setCryptoLoading] = useState(false)
  const [starsLoading, setStarsLoading] = useState(false)
  const [cryptoError, setCryptoError] = useState<string | null>(null)
  const [heleketAmount, setHeleketAmount] = useState(0)
  const [customUsdH, setCustomUsdH] = useState('')
  const [heleketLoading, setHeleketLoading] = useState(false)
  const [heleketError, setHeleketError] = useState<string | null>(null)
  const [starsError, setStarsError] = useState<string | null>(null)
  const [topupSuccess, setTopupSuccess] = useState<number | null>(null)

  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

  const stars = me.balance_stars
  const usdDisplay = (stars * 0.013).toFixed(2)

  const payLabel = lang === 'ru' ? 'Пополнить' : lang === 'ua' ? 'Поповнити' : 'Pay'
  const afterLabel = lang === 'ru' ? 'Баланс зачисляется автоматически' : lang === 'ua' ? 'Баланс зараховується автоматично' : 'Balance credited automatically'

  async function payCrypto(amount: number) {
    if (amount < 0.1) return
    setCryptoLoading(true); setCryptoError(null)
    try {
      const { url } = await api.cryptoCreate(amount)
      if (window.Telegram?.WebApp) window.Telegram.WebApp.openLink(url)
      else window.open(url, '_blank')
    } catch (e: any) { setCryptoError(e.message ?? 'Error') }
    finally { setCryptoLoading(false) }
  }

  async function payHeleket(amount: number) {
    if (amount < 0.1) return
    setHeleketLoading(true); setHeleketError(null)
    try {
      const { url } = await api.heleketCreate(amount)
      if (window.Telegram?.WebApp) window.Telegram.WebApp.openLink(url)
      else window.open(url, '_blank')
    } catch (e: any) { setHeleketError(e.message ?? 'Error') }
    finally { setHeleketLoading(false) }
  }

  async function payStars(count: number) {
    if (count < 1 || starsLoading) return
    setStarsLoading(true); setStarsError(null)
    try {
      const { invoice_url } = await api.starsInvoice(count)
      if (window.Telegram?.WebApp) {
        // openInvoice повертається ОДРАЗУ — НЕ ставити setStarsLoading(false) у finally.
        // Кнопка лишається заблокованою до завершення платежу (paid/cancelled/failed).
        window.Telegram.WebApp.openInvoice(invoice_url, status => {
          setStarsLoading(false)
          if (status === 'paid') {
            setOpen(null)
            setTopupSuccess(count)
            setTimeout(() => setTopupSuccess(null), 4000)
          } else if (status === 'cancelled' || status === 'failed') {
            setStarsError(T.stars_failed)
          }
        })
      } else {
        window.open(invoice_url, '_blank')
        setStarsLoading(false)
      }
    } catch (e: any) {
      setStarsError(e.message ?? 'Error')
      setStarsLoading(false)
    }
  }

  async function redeemPromo() {
    if (!promoCode.trim() || promoLoading) return
    setPromoLoading(true); setPromoResult(null)
    try {
      const res = await api.promoRedeem(promoCode.trim())
      setPromoResult({ ok: true, stars: res.stars })
      setPromoCode('')
    } catch (e: any) {
      const msg = e.message ?? ''
      const errText =
        msg === 'promo_not_found'    ? (lang === 'ru' ? 'Промокод не найден' : lang === 'ua' ? 'Промокод не знайдено' : 'Promo code not found') :
        msg === 'promo_limit_reached' ? (lang === 'ru' ? 'Промокод уже исчерпан' : lang === 'ua' ? 'Промокод вичерпано' : 'Promo code exhausted') :
        msg === 'promo_already_used'  ? (lang === 'ru' ? 'Вы уже использовали этот промокод' : lang === 'ua' ? 'Ви вже використали цей промокод' : 'Already used') :
        (lang === 'ru' ? 'Ошибка активации' : lang === 'ua' ? 'Помилка активації' : 'Activation error')
      setPromoResult({ ok: false, error: errText })
    } finally { setPromoLoading(false) }
  }

  function toggleCrypto() {
    if (open === 'crypto') { setOpen(null); return }
    setCryptoError(null); setCryptoAmount(0); setCustomUsd(''); setOpen('crypto')
  }
  function toggleHeleket() {
    if (open === 'heleket') { setOpen(null); return }
    setHeleketError(null); setHeleketAmount(0); setCustomUsdH(''); setOpen('heleket')
  }
  function toggleStars() {
    if (open === 'stars') { setOpen(null); return }
    setStarsError(null); setStarsCount(0); setCustomStars(''); setOpen('stars')
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
    <div className="page" style={{ paddingTop: 12 }}>
      <style>{SLIDE_STYLE}</style>

      {/* Success toast */}
      {topupSuccess && (
        <div style={{
          position: 'fixed', top: 24, left: '50%', zIndex: 999,
          animation: 'topup-pop .45s cubic-bezier(.32,1,.6,1)',
          background: 'linear-gradient(135deg, #1a180a, #1a1600)',
          border: '2px solid rgba(255,184,48,.6)',
          borderRadius: 18, padding: '14px 22px',
          display: 'flex', alignItems: 'center', gap: 14,
          boxShadow: '0 8px 40px rgba(0,0,0,.7)',
          transform: 'translateX(-50%)',
          pointerEvents: 'none',
        }}>
          <span style={{ fontSize: 32, animation: 'star-spin .6s ease' }}>⭐</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16, color: '#FFB830' }}>
              +{topupSuccess} {lang === 'ru' ? 'звёзд зачислено!' : lang === 'ua' ? 'зірок зараховано!' : 'Stars credited!'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              {lang === 'ru' ? 'Баланс обновится при следующем открытии' : lang === 'ua' ? 'Баланс оновиться при наступному відкритті' : 'Balance updates on next open'}
            </div>
          </div>
        </div>
      )}

      <h1 style={{ marginBottom: 16 }}>{T.balance}</h1>

      {/* Balance hero — Stars primary */}
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
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1, position: 'relative', display: 'inline-block' }}>
            <span style={{ fontWeight: 800, fontSize: 40 }}>⭐{stars}</span>
            <span style={{ fontWeight: 400, fontSize: 15, marginLeft: 10, color: 'var(--muted)' }}>(${usdDisplay})</span>
            {balanceDiff && (
              <span style={{
                position: 'absolute', top: -8, right: -48,
                color: '#4cff8f', fontWeight: 800, fontSize: 18,
                animation: 'balance-plus 2.5s ease forwards',
                pointerEvents: 'none', whiteSpace: 'nowrap',
              }}>+{balanceDiff}⭐</span>
            )}
          </div>
          <BioPromoButton lang={lang} />
        </div>
      </div>

      {/* Section label */}
      <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 8, paddingLeft: 4 }}>
        {lang === 'ru' ? 'СПОСОБЫ ПОПОЛНЕНИЯ' : lang === 'ua' ? 'СПОСОБИ ПОПОВНЕННЯ' : 'TOP UP METHODS'}
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
                  style={{ ...presetBtn(cryptoAmount === p && !customUsd), lineHeight: 1.3 }}>
                  <div>${p}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, opacity: 0.7 }}>⭐{Math.round(p / 0.013)}</div>
                </button>
              ))}
            </div>
            <input
              type="number" min="0.1" step="0.1"
              placeholder={lang === 'ua' ? 'Сума від $0.10' : lang === 'ru' ? 'Сумма от $0.10' : 'Amount from $0.10'}
              value={customUsd}
              onChange={e => { setCustomUsd(e.target.value); setCryptoAmount(parseFloat(e.target.value) || 0) }}
              style={{ ...inputStyle, marginBottom: cryptoAmount > 0 ? 6 : 10 }}
            />
            {cryptoAmount > 0 && (
              <div style={{ fontSize: 13, color: '#26A17B', fontWeight: 600, marginBottom: 10, textAlign: 'center' }}>
                ${cryptoAmount.toFixed(2)} = <b>⭐{Math.round(cryptoAmount / 0.013)}</b>
              </div>
            )}
            {cryptoError && <div style={{ marginBottom: 8, fontSize: 13, color: 'var(--red)' }}>{cryptoError}</div>}
            <button className="btn btn-primary" disabled={cryptoAmount < 0.1 || cryptoLoading}
              onClick={() => payCrypto(cryptoAmount)}
              style={{ background: 'linear-gradient(135deg, #26A17B, #1a7a5e)' }}>
              {cryptoLoading ? '⏳...' : cryptoAmount >= 0.1
                ? `${payLabel} $${cryptoAmount.toFixed(2)} → ⭐${Math.round(cryptoAmount / 0.013)}`
                : payLabel}
            </button>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>{afterLabel}</div>
          </ExpandPanel>
        )}
      </div>

      {/* Heleket card */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(99,102,241,.08), rgba(99,102,241,.03))',
        border: '1px solid rgba(99,102,241,.22)',
        borderRadius: 14, marginBottom: 8, overflow: 'hidden',
      }}>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', cursor: 'pointer' }}
          onClick={toggleHeleket}
        >
          <div style={{
            width: 38, height: 38, borderRadius: 11, flexShrink: 0,
            background: 'rgba(99,102,241,.15)', border: '1px solid rgba(99,102,241,.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
          }}>🪙</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15, color: '#818cf8' }}>Heleket</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              {lang === 'ru' ? 'Криптовалюта' : lang === 'ua' ? 'Криптовалюта' : 'Cryptocurrency'} · USDT · BTC · TON
            </div>
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 18, transition: 'transform .2s', transform: open === 'heleket' ? 'rotate(90deg)' : '' }}>›</div>
        </div>

        {open === 'heleket' && (
          <ExpandPanel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
              {PRESETS_USD.map(p => (
                <button key={p} onClick={() => { setHeleketAmount(p); setCustomUsdH('') }}
                  style={{ ...presetBtn(heleketAmount === p && !customUsdH), lineHeight: 1.3 }}>
                  <div>${p}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, opacity: 0.7 }}>⭐{Math.round(p / 0.013)}</div>
                </button>
              ))}
            </div>
            <input
              type="number" min="0.1" step="0.1"
              placeholder={lang === 'ua' ? 'Сума від $0.10' : lang === 'ru' ? 'Сумма от $0.10' : 'Amount from $0.10'}
              value={customUsdH}
              onChange={e => { setCustomUsdH(e.target.value); setHeleketAmount(parseFloat(e.target.value) || 0) }}
              style={{ ...inputStyle, marginBottom: heleketAmount > 0 ? 6 : 10 }}
            />
            {heleketAmount > 0 && (
              <div style={{ fontSize: 13, color: '#818cf8', fontWeight: 600, marginBottom: 10, textAlign: 'center' }}>
                ${heleketAmount.toFixed(2)} = <b>⭐{Math.round(heleketAmount / 0.013)}</b>
              </div>
            )}
            {heleketError && <div style={{ marginBottom: 8, fontSize: 13, color: 'var(--red)' }}>{heleketError}</div>}
            <button className="btn btn-primary" disabled={heleketAmount < 0.1 || heleketLoading}
              onClick={() => payHeleket(heleketAmount)}
              style={{ background: 'linear-gradient(135deg, #6366f1, #4f46e5)' }}>
              {heleketLoading ? '⏳...' : heleketAmount >= 0.1
                ? `${payLabel} $${heleketAmount.toFixed(2)} → ⭐${Math.round(heleketAmount / 0.013)}`
                : payLabel}
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
              {PRESETS_STARS.map(s => (
                <button key={s} onClick={() => { setStarsCount(s); setCustomStars(String(s)) }}
                  style={presetBtn(customStars === String(s))}>
                  ⭐{s}
                </button>
              ))}
            </div>
            <input
              type="number" min="1" step="1"
              placeholder={lang === 'ru' ? 'Кол-во звёзд (⭐)' : lang === 'ua' ? 'Кількість зірок (⭐)' : 'Stars amount (⭐)'}
              value={customStars}
              onChange={e => {
                const s = Math.max(0, parseInt(e.target.value) || 0)
                setCustomStars(e.target.value)
                setStarsCount(s)
              }}
              style={{ ...inputStyle, marginBottom: 10 }}
            />
            {starsError && <div style={{ marginBottom: 8, fontSize: 13, color: 'var(--red)' }}>{starsError}</div>}
            <button className="btn btn-primary" disabled={starsCount < 1 || starsLoading}
              onClick={() => payStars(starsCount)}
              style={{ background: 'linear-gradient(135deg, #FFB830, #e09000)' }}>
              {starsLoading ? '⏳...' : starsCount >= 1 ? `${payLabel} ⭐${starsCount}` : payLabel}
            </button>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>
              {lang === 'ru' ? 'Оплата через Telegram Stars' : lang === 'ua' ? 'Оплата через Telegram Stars' : 'Pay via Telegram Stars'}
            </div>
          </ExpandPanel>
        )}
      </div>

      {/* Promo code */}
      <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, margin: '16px 0 8px', paddingLeft: 4 }}>
        {lang === 'ru' ? 'ПРОМОКОД' : lang === 'ua' ? 'ПРОМОКОД' : 'PROMO CODE'}
      </div>
      <div style={{
        background: 'linear-gradient(135deg, rgba(255,107,43,.06), rgba(255,107,43,.02))',
        border: '1px solid rgba(255,107,43,.2)',
        borderRadius: 14, padding: '14px 16px',
      }}>
        <input
          type="text"
          placeholder={lang === 'ru' ? 'Введите промокод...' : lang === 'ua' ? 'Введіть промокод...' : 'Enter promo code...'}
          value={promoCode}
          onChange={e => { setPromoCode(e.target.value); setPromoResult(null) }}
          onKeyDown={e => e.key === 'Enter' && redeemPromo()}
          style={{
            width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '13px 16px', color: 'var(--text)',
            fontSize: 16, fontWeight: 700, letterSpacing: 2, outline: 'none',
            boxSizing: 'border-box', marginBottom: 10, textAlign: 'center',
          }}
        />
        <button
          className="btn btn-primary"
          style={{ width: '100%', fontSize: 15, padding: '13px' }}
          disabled={!promoCode.trim() || promoLoading}
          onClick={redeemPromo}
        >
          {promoLoading ? '⏳ ...' : (lang === 'ru' ? '🎟 Активировать промокод' : lang === 'ua' ? '🎟 Активувати промокод' : '🎟 Activate promo code')}
        </button>
        {promoResult?.ok && (
          <div style={{ marginTop: 10, padding: '10px 14px', background: 'rgba(76,175,114,.12)', border: '1px solid rgba(76,175,114,.3)', borderRadius: 10, color: '#4CAF72', fontWeight: 700, fontSize: 14 }}>
            ✅ +{promoResult.stars}⭐ {lang === 'ru' ? 'начислено!' : lang === 'ua' ? 'зараховано!' : 'credited!'}
          </div>
        )}
        {promoResult?.error && (
          <div style={{ marginTop: 10, padding: '10px 14px', background: 'rgba(255,59,48,.08)', border: '1px solid rgba(255,59,48,.25)', borderRadius: 10, color: 'var(--red)', fontSize: 13 }}>
            ❌ {promoResult.error}
          </div>
        )}
      </div>

      <LegalFooter />
    </div>
  )
}
