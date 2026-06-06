import { useState, useEffect } from 'react'
import { bioPromoApi, type BioPromoStatus } from '../api'
import { getT, type Lang } from '../i18n'

const USERNAME = '@LEMUR_SHOP'
const PHRASES: Record<'ua' | 'ru' | 'en', string> = {
  ua: 'Дешеві акаунти та накрутка тільки в @LEMUR_SHOP',
  ru: 'Дешёвые аккаунты и накрутка только в @LEMUR_SHOP',
  en: 'Cheap accounts and promotion only at @LEMUR_SHOP',
}

interface Props { lang: Lang }

function TgProfileMockup({ lang, variant }: { lang: Lang; variant: 1 | 2 }) {
  const label     = lang === 'ru' ? 'О себе' : lang === 'en' ? 'About' : 'Про себе'
  const editTitle = lang === 'ru' ? 'Редактировать профиль' : lang === 'en' ? 'Edit Profile' : 'Редагувати профіль'
  const hint      = lang === 'ru' ? '← вставь сюда' : lang === 'en' ? '← paste here' : '← встав сюди'
  const bioText   = variant === 2 ? PHRASES[lang] : USERNAME
  const color     = variant === 2 ? '#FFB347' : '#5fba47'
  const colorA    = variant === 2 ? 'rgba(255,179,71,' : 'rgba(95,186,71,'
  return (
    <div style={{
      background: '#212121', borderRadius: 16, overflow: 'hidden',
      border: '1px solid rgba(255,255,255,.1)', marginBottom: 14, fontSize: 13,
    }}>
      <div style={{
        background: '#2b2b2b', padding: '10px 14px',
        display: 'flex', alignItems: 'center', gap: 10,
        borderBottom: '1px solid rgba(255,255,255,.07)',
      }}>
        <div style={{ fontSize: 18, color: '#2AABEE' }}>‹</div>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>{editTitle}</div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', padding: '14px 0 10px' }}>
        <div style={{
          width: 60, height: 60, borderRadius: '50%',
          background: 'linear-gradient(135deg, #2AABEE, #1178B8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26,
        }}>🦎</div>
      </div>
      {[
        { label: lang === 'ru' ? 'Имя' : lang === 'en' ? 'First name' : 'Ім\'я', value: 'LEMUR', muted: false },
        { label: lang === 'ru' ? 'Фамилия' : lang === 'en' ? 'Last name' : 'Прізвище', value: '—', muted: true },
      ].map(f => (
        <div key={f.label} style={{
          padding: '8px 14px', borderBottom: '1px solid rgba(255,255,255,.05)',
          display: 'flex', justifyContent: 'space-between',
        }}>
          <span style={{ color: '#2AABEE', fontSize: 12 }}>{f.label}</span>
          <span style={{ color: f.muted ? '#555' : '#fff', fontSize: 12 }}>{f.value}</span>
        </div>
      ))}
      <div style={{
        padding: '10px 14px',
        background: `${colorA}.1)`,
        border: `1.5px solid ${colorA}.5)`,
        borderRadius: 8, margin: '6px 8px 8px',
      }}>
        <div style={{ color, fontSize: 11, marginBottom: 4, fontWeight: 700 }}>{label}</div>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6 }}>
          <code style={{ color: '#fff', fontSize: variant === 2 ? 11 : 14, fontWeight: 700, lineHeight: 1.5, wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
            {bioText}
          </code>
          <span style={{ color, fontSize: 11, fontWeight: 700, flexShrink: 0, marginTop: 2 }}>{hint}</span>
        </div>
      </div>
    </div>
  )
}

export default function BioPromoButton({ lang }: Props) {
  const T = getT(lang)
  const [promo, setPromo]       = useState<BioPromoStatus | null>(null)
  const [open, setOpen]         = useState(false)
  const [loading, setLoading]   = useState(false)
  const [msg, setMsg]           = useState('')
  const [variant, setVariant]   = useState<1 | 2>(2)

  useEffect(() => {
    bioPromoApi.status().then(setPromo).catch(() => {})
  }, [])

  async function doCheck() {
    setLoading(true); setMsg('')
    try {
      const res = await bioPromoApi.check()
      setPromo(res)
      if (res.rewarded) {
        setMsg(res.reward_tier === 2 ? T.bio_promo_rewarded2 : T.bio_promo_rewarded)
      } else if (!res.is_active) {
        setMsg(T.bio_promo_not_active)
      } else if ((res.hours_until_next ?? 0) > 0) {
        setMsg(T.bio_promo_wait(res.hours_until_next!))
      } else {
        setMsg(res.reward_tier === 2 ? T.bio_promo_ok2 : T.bio_promo_ok)
      }
    } catch { setMsg(T.bio_promo_error) }
    setLoading(false)
  }

  function close() { setOpen(false); setMsg('') }

  const active = promo?.is_active
  const tier   = promo?.reward_tier ?? 0

  return (
    <>
      {/* Main button — always shows +2⭐ as max potential */}
      <button
        onClick={() => setOpen(true)}
        style={{
          background: active
            ? tier === 2
              ? 'linear-gradient(135deg, rgba(255,179,71,.35) 0%, rgba(200,120,0,.25) 100%)'
              : 'linear-gradient(135deg, rgba(95,186,71,.35) 0%, rgba(40,120,20,.25) 100%)'
            : 'linear-gradient(135deg, rgba(255,165,0,.18) 0%, rgba(200,100,0,.12) 100%)',
          border: active
            ? tier === 2 ? '1.5px solid rgba(255,179,71,.7)' : '1.5px solid rgba(95,186,71,.7)'
            : '1.5px solid rgba(255,165,0,.45)',
          borderRadius: 16, padding: '12px 20px', cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
          boxShadow: active
            ? tier === 2
              ? '0 0 20px rgba(255,179,71,.4), 0 2px 8px rgba(0,0,0,.3)'
              : '0 0 20px rgba(95,186,71,.35), 0 2px 8px rgba(0,0,0,.3)'
            : '0 0 16px rgba(255,165,0,.2), 0 2px 8px rgba(0,0,0,.3)',
          minWidth: 80, position: 'relative', overflow: 'hidden',
        }}>
        <div style={{
          position: 'absolute', inset: 0, borderRadius: 16,
          background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,.08) 50%, transparent 60%)',
          pointerEvents: 'none',
        }} />
        <span style={{
          fontSize: 26, fontWeight: 900, lineHeight: 1, color: '#FFB347',
          textShadow: '0 0 12px rgba(255,179,71,.7)',
        }}>+2⭐</span>
        <span style={{ fontSize: 11, color: '#ffd080', fontWeight: 700, whiteSpace: 'nowrap' }}>
          {T.bio_promo_daily}
        </span>
        <span style={{ fontSize: 10, color: 'rgba(255,208,128,.6)', fontWeight: 600, whiteSpace: 'nowrap' }}>
          {T.bio_promo_daily_sub}
        </span>
      </button>

      {/* Modal */}
      {open && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(0,0,0,.78)',
          display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
          backdropFilter: 'blur(6px)',
        }} onClick={close}>
          <div onClick={e => e.stopPropagation()} style={{
            width: '100%', maxWidth: 480,
            background: 'linear-gradient(160deg, #1A2018 0%, #141018 100%)',
            border: '1px solid rgba(95,186,71,.25)',
            borderRadius: '24px 24px 0 0',
            padding: '16px 20px 36px',
            maxHeight: '90vh', overflowY: 'auto',
          }}>
            {/* Drag handle + close */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ width: 28 }} />
              <div style={{ width: 40, height: 4, borderRadius: 4, background: 'rgba(255,255,255,.15)' }} />
              <button onClick={close} style={{
                background: 'rgba(255,255,255,.08)', border: '1px solid rgba(255,255,255,.12)',
                borderRadius: 8, width: 28, height: 28, cursor: 'pointer',
                color: 'rgba(255,255,255,.6)', fontSize: 16, lineHeight: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 0, flexShrink: 0,
              }}>✕</button>
            </div>

            {/* ── Variant selector — TOP ── */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 18 }}>
              <button onClick={() => setVariant(1)} style={{
                flex: 1, padding: '10px 8px', borderRadius: 12, cursor: 'pointer',
                fontWeight: variant === 1 ? 800 : 500, fontSize: 13,
                background: variant === 1 ? 'rgba(95,186,71,.2)' : 'rgba(255,255,255,.04)',
                border: variant === 1 ? '1.5px solid rgba(95,186,71,.55)' : '1.5px solid rgba(255,255,255,.1)',
                color: variant === 1 ? '#7ee85a' : 'var(--muted)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
              }}>
                <span style={{ fontSize: 18, fontWeight: 900 }}>+1⭐</span>
                <span style={{ fontSize: 10 }}>{lang === 'ru' ? 'Вариант 1' : lang === 'en' ? 'Option 1' : 'Варіант 1'}</span>
                <span style={{ fontSize: 9, opacity: .7 }}>{lang === 'ru' ? 'только юзернейм' : lang === 'en' ? 'username only' : 'тільки юзернейм'}</span>
              </button>
              <button onClick={() => setVariant(2)} style={{
                flex: 1, padding: '10px 8px', borderRadius: 12, cursor: 'pointer',
                fontWeight: variant === 2 ? 800 : 500, fontSize: 13,
                background: variant === 2 ? 'rgba(255,179,71,.22)' : 'rgba(255,255,255,.04)',
                border: variant === 2 ? '1.5px solid rgba(255,179,71,.6)' : '1.5px solid rgba(255,255,255,.1)',
                color: variant === 2 ? '#FFB347' : 'var(--muted)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
              }}>
                <span style={{ fontSize: 18, fontWeight: 900 }}>+2⭐</span>
                <span style={{ fontSize: 10 }}>{lang === 'ru' ? 'Вариант 2' : lang === 'en' ? 'Option 2' : 'Варіант 2'}</span>
                <span style={{ fontSize: 9, opacity: .7 }}>{lang === 'ru' ? 'полная фраза' : lang === 'en' ? 'full phrase' : 'повна фраза'}</span>
              </button>
            </div>

            <div style={{ fontWeight: 800, fontSize: 18, textAlign: 'center', marginBottom: 6 }}>{T.bio_promo_title}</div>
            <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', marginBottom: 16, lineHeight: 1.5 }}>
              {T.bio_promo_desc}
            </div>

            {/* Copy section */}
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, letterSpacing: .5 }}>{T.bio_promo_add_label}</div>

            {variant === 1 ? (
              /* Variant 1: single username */
              <div style={{
                background: 'rgba(95,186,71,.08)', border: '1.5px dashed rgba(95,186,71,.4)',
                borderRadius: 14, padding: '12px 14px', marginBottom: 14,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <code style={{
                    flex: 1, fontSize: 18, fontWeight: 800, color: '#5fba47',
                    background: 'rgba(95,186,71,.12)', borderRadius: 8, padding: '6px 10px', textAlign: 'center',
                  }}>{USERNAME}</code>
                  <button
                    onClick={() => { navigator.clipboard?.writeText(USERNAME); setMsg('📋 ' + T.copied) }}
                    style={{
                      background: 'rgba(95,186,71,.2)', border: '1px solid rgba(95,186,71,.4)',
                      borderRadius: 10, padding: '8px 12px', cursor: 'pointer',
                      color: '#5fba47', fontSize: 12, fontWeight: 700, flexShrink: 0,
                    }}>{T.copy}</button>
                </div>
              </div>
            ) : (
              /* Variant 2: 3-language phrases */
              <div style={{
                background: 'rgba(255,179,71,.06)', border: '1.5px dashed rgba(255,179,71,.35)',
                borderRadius: 14, padding: '12px 14px', marginBottom: 14,
              }}>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10 }}>{T.bio_promo_phrase_hint}</div>
                {(['ua', 'ru', 'en'] as const).map((l, i) => {
                  const flag   = l === 'ua' ? '🇺🇦' : l === 'ru' ? '🇷🇺' : '🇬🇧'
                  const phrase = PHRASES[l]
                  // Split phrase so @LEMUR_SHOP is on a new line
                  const parts  = phrase.split('@LEMUR_SHOP')
                  return (
                    <div key={l} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      marginBottom: i < 2 ? 10 : 0,
                      paddingBottom: i < 2 ? 10 : 0,
                      borderBottom: i < 2 ? '1px solid rgba(255,179,71,.12)' : 'none',
                    }}>
                      <span style={{ fontSize: 18, flexShrink: 0 }}>{flag}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 11, color: 'rgba(255,255,255,.7)', lineHeight: 1.4 }}>
                          {parts[0]}
                        </div>
                        <code style={{ fontSize: 13, fontWeight: 800, color: '#FFB347' }}>
                          @LEMUR_SHOP
                        </code>
                      </div>
                      <button
                        onClick={() => { navigator.clipboard?.writeText(phrase); setMsg('📋 ' + T.copied) }}
                        style={{
                          background: 'rgba(255,179,71,.2)', border: '1px solid rgba(255,179,71,.4)',
                          borderRadius: 7, padding: '7px 11px', cursor: 'pointer',
                          color: '#FFB347', fontSize: 12, fontWeight: 700, flexShrink: 0,
                        }}>📋</button>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Mockup */}
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, letterSpacing: .5 }}>{T.bio_promo_how_label}</div>
            <TgProfileMockup lang={lang} variant={variant} />

            {/* Steps */}
            <div style={{
              background: 'rgba(255,255,255,.03)', border: '1px solid var(--border)',
              borderRadius: 14, padding: '12px 14px', marginBottom: 14,
            }}>
              {([
                ['1', T.bio_promo_step1],
                ['2', T.bio_promo_step2],
                ['3', T.bio_promo_step3],
              ] as [string, string][]).map(([n, t]) => (
                <div key={n} style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: n === '3' ? 0 : 8 }}>
                  <div style={{
                    width: 22, height: 22, borderRadius: 8, background: 'rgba(95,186,71,.15)',
                    border: '1px solid rgba(95,186,71,.3)', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontSize: 11, fontWeight: 800, color: '#5fba47', flexShrink: 0,
                  }}>{n}</div>
                  <div style={{ fontSize: 12, lineHeight: 1.4 }}>{t}</div>
                </div>
              ))}
            </div>

            {/* Status */}
            {promo?.joined && (
              <div style={{
                background: promo.is_active
                  ? (promo.reward_tier === 2 ? 'rgba(255,179,71,.1)' : 'rgba(95,186,71,.1)')
                  : 'rgba(255,80,80,.08)',
                border: `1px solid ${promo.is_active
                  ? (promo.reward_tier === 2 ? 'rgba(255,179,71,.35)' : 'rgba(95,186,71,.3)')
                  : 'rgba(255,80,80,.25)'}`,
                borderRadius: 14, padding: '12px 14px', marginBottom: 14,
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>
                    {promo.is_active
                      ? (promo.reward_tier === 2 ? T.bio_promo_active2 : T.bio_promo_active)
                      : T.bio_promo_inactive}
                  </div>
                  {promo.is_active && promo.hours_until_next !== null && promo.hours_until_next > 0 && (
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                      {T.bio_promo_next_hrs(promo.hours_until_next)}
                    </div>
                  )}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--orange)' }}>⭐{promo.total_rewarded}</div>
                  <div style={{ fontSize: 10, color: 'var(--muted)' }}>{T.bio_promo_earned}</div>
                </div>
              </div>
            )}

            {msg && (
              <div style={{
                fontSize: 13, textAlign: 'center', marginBottom: 12,
                color: msg.startsWith('✅') || msg.startsWith('📋') ? '#5fba47' : msg.startsWith('❌') ? '#ff6060' : 'var(--muted)',
              }}>{msg}</div>
            )}

            <button
              className="btn btn-primary"
              style={{ width: '100%', opacity: loading ? .6 : 1 }}
              disabled={loading}
              onClick={doCheck}
            >
              {loading ? T.bio_promo_checking : promo?.joined && promo?.is_active ? T.bio_promo_recheck : T.bio_promo_check_btn}
            </button>
          </div>
        </div>
      )}
    </>
  )
}
