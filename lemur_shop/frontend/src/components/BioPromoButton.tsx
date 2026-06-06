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

function TgProfileMockup({ lang, tier }: { lang: Lang; tier: 1 | 2 }) {
  const label     = lang === 'ru' ? 'О себе' : lang === 'en' ? 'About' : 'Про себе'
  const editTitle = lang === 'ru' ? 'Редактировать профиль' : lang === 'en' ? 'Edit Profile' : 'Редагувати профіль'
  const hint      = lang === 'ru' ? '← вставь сюда' : lang === 'en' ? '← paste here' : '← встав сюди'
  const bioText   = tier === 2 ? PHRASES[lang] : USERNAME
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
        background: tier === 2 ? 'rgba(255,179,71,.1)' : 'rgba(95,186,71,.1)',
        border: `1.5px solid ${tier === 2 ? 'rgba(255,179,71,.5)' : 'rgba(95,186,71,.5)'}`,
        borderRadius: 8, margin: '6px 8px 8px',
      }}>
        <div style={{ color: tier === 2 ? '#FFB347' : '#5fba47', fontSize: 11, marginBottom: 4, fontWeight: 700 }}>{label}</div>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6 }}>
          <code style={{ color: '#fff', fontSize: tier === 2 ? 11 : 14, fontWeight: 700, lineHeight: 1.4 }}>{bioText}</code>
          <span style={{ color: tier === 2 ? '#FFB347' : '#5fba47', fontSize: 11, fontWeight: 700, flexShrink: 0 }}>{hint}</span>
        </div>
      </div>
    </div>
  )
}

function CopyCard({
  label, hint, value, color, stars, onCopy,
}: {
  label: string; hint: string; value: string; color: string; stars: string; onCopy: () => void
}) {
  return (
    <div style={{
      background: `rgba(${color},.08)`, border: `1.5px dashed rgba(${color},.4)`,
      borderRadius: 14, padding: '12px 14px', flex: 1,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: .5 }}>{label}</div>
        <div style={{ fontSize: 12, fontWeight: 800, color: `rgba(${color},1)` }}>{stars}</div>
      </div>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, lineHeight: 1.4 }}>{hint}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <code style={{
          fontSize: 11, fontWeight: 700, color: `rgba(${color},1)`,
          background: `rgba(${color},.12)`, borderRadius: 6, padding: '4px 8px',
          flex: 1, wordBreak: 'break-all', lineHeight: 1.4,
        }}>{value}</code>
        <button onClick={onCopy} style={{
          background: `rgba(${color},.2)`, border: `1px solid rgba(${color},.4)`,
          borderRadius: 8, padding: '6px 10px', cursor: 'pointer', color: `rgba(${color},1)`,
          fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap', flexShrink: 0,
        }}>📋</button>
      </div>
    </div>
  )
}

export default function BioPromoButton({ lang }: Props) {
  const T = getT(lang)
  const [promo, setPromo]     = useState<BioPromoStatus | null>(null)
  const [open, setOpen]       = useState(false)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg]         = useState('')
  const [mockupTier, setMockupTier] = useState<1 | 2>(1)

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
  const starsLabel = tier === 2 ? '+2⭐' : '+1⭐'

  return (
    <>
      {/* Main button */}
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
          fontSize: 26, fontWeight: 900, lineHeight: 1,
          color: active ? (tier === 2 ? '#FFB347' : '#7ee85a') : '#FFB347',
          textShadow: active
            ? tier === 2 ? '0 0 12px rgba(255,179,71,.7)' : '0 0 12px rgba(95,186,71,.7)'
            : '0 0 10px rgba(255,179,71,.6)',
        }}>{starsLabel}</span>
        <span style={{ fontSize: 11, color: active ? (tier === 2 ? '#ffd080' : '#a8f080') : '#ffd080', fontWeight: 700, whiteSpace: 'nowrap' }}>
          {T.bio_promo_daily}
        </span>
        <span style={{ fontSize: 10, color: active ? (tier === 2 ? 'rgba(255,208,128,.7)' : 'rgba(168,240,128,.7)') : 'rgba(255,208,128,.6)', fontWeight: 600, whiteSpace: 'nowrap' }}>
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
            {/* Header: drag handle + close */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
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

            <div style={{ fontWeight: 800, fontSize: 18, textAlign: 'center', marginBottom: 6 }}>{T.bio_promo_title}</div>
            <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', marginBottom: 16, lineHeight: 1.5 }}>
              {T.bio_promo_desc}
            </div>

            {/* Variant 1 — username only */}
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, letterSpacing: .5 }}>{T.bio_promo_add_label}</div>
            <CopyCard
              label={lang === 'ru' ? 'ВАРИАНТ 1 — только юзернейм' : lang === 'en' ? 'OPTION 1 — username only' : 'ВАРІАНТ 1 — тільки юзернейм'}
              hint={lang === 'ru' ? 'Только @LEMUR_SHOP в «О себе»' : lang === 'en' ? 'Only @LEMUR_SHOP in About' : 'Тільки @LEMUR_SHOP в «Про себе»'}
              value={USERNAME}
              color="95,186,71"
              stars="+1⭐/день"
              onCopy={() => { navigator.clipboard?.writeText(USERNAME); setMsg('📋 ' + T.copied) }}
            />

            {/* Variant 2 — full phrase, 3 languages */}
            <div style={{ fontSize: 11, color: '#FFB347', marginTop: 14, marginBottom: 8, letterSpacing: .5, fontWeight: 700 }}>
              {T.bio_promo_phrase_label}
            </div>
            <div style={{
              background: 'rgba(255,179,71,.06)', border: '1.5px dashed rgba(255,179,71,.35)',
              borderRadius: 14, padding: '10px 12px', marginBottom: 14,
            }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>{T.bio_promo_phrase_hint}</div>
              {(['ua', 'ru', 'en'] as const).map((l) => {
                const flag = l === 'ua' ? '🇺🇦' : l === 'ru' ? '🇷🇺' : '🇬🇧'
                const phrase = PHRASES[l]
                return (
                  <div key={l} style={{
                    display: 'flex', alignItems: 'center', gap: 8, marginBottom: l === 'en' ? 0 : 8,
                  }}>
                    <span style={{ fontSize: 16, flexShrink: 0 }}>{flag}</span>
                    <code style={{
                      flex: 1, fontSize: 10, color: '#FFB347', lineHeight: 1.4,
                      background: 'rgba(255,179,71,.1)', borderRadius: 6, padding: '4px 8px',
                      wordBreak: 'break-all',
                    }}>{phrase}</code>
                    <button
                      onClick={() => { navigator.clipboard?.writeText(phrase); setMsg('📋 ' + T.copied) }}
                      style={{
                        background: 'rgba(255,179,71,.2)', border: '1px solid rgba(255,179,71,.4)',
                        borderRadius: 7, padding: '5px 9px', cursor: 'pointer',
                        color: '#FFB347', fontSize: 11, fontWeight: 700, flexShrink: 0,
                      }}>📋</button>
                  </div>
                )
              })}
            </div>

            {/* Mockup switcher */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
              {([1, 2] as const).map(t => (
                <button key={t} onClick={() => setMockupTier(t)} style={{
                  flex: 1, padding: '6px 0', fontSize: 11, fontWeight: mockupTier === t ? 700 : 500,
                  background: mockupTier === t
                    ? t === 2 ? 'rgba(255,179,71,.2)' : 'rgba(95,186,71,.2)'
                    : 'rgba(255,255,255,.04)',
                  border: mockupTier === t
                    ? t === 2 ? '1px solid rgba(255,179,71,.4)' : '1px solid rgba(95,186,71,.4)'
                    : '1px solid var(--border)',
                  borderRadius: 8, cursor: 'pointer',
                  color: mockupTier === t ? (t === 2 ? '#FFB347' : '#5fba47') : 'var(--muted)',
                }}>
                  {t === 1
                    ? (lang === 'ru' ? 'Вариант 1 (+1⭐)' : lang === 'en' ? 'Option 1 (+1⭐)' : 'Варіант 1 (+1⭐)')
                    : (lang === 'ru' ? 'Вариант 2 (+2⭐)' : lang === 'en' ? 'Option 2 (+2⭐)' : 'Варіант 2 (+2⭐)')}
                </button>
              ))}
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, letterSpacing: .5 }}>{T.bio_promo_how_label}</div>
            <TgProfileMockup lang={lang} tier={mockupTier} />

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

            {/* Status (if joined) */}
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
