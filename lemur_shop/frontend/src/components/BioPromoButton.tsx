import { useState, useEffect } from 'react'
import { bioPromoApi, type BioPromoStatus } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang }

function TgProfileMockup({ lang }: { lang: Lang }) {
  const label = lang === 'ru' ? 'О себе' : lang === 'en' ? 'About' : 'Про себе'
  const editTitle = lang === 'ru' ? 'Редактировать профиль' : lang === 'en' ? 'Edit Profile' : 'Редагувати профіль'
  const hint = lang === 'ru' ? '← вставь сюда' : lang === 'en' ? '← paste here' : '← встав сюди'
  return (
    <div style={{
      background: '#212121', borderRadius: 16, overflow: 'hidden',
      border: '1px solid rgba(255,255,255,.1)', marginBottom: 14,
      fontSize: 13,
    }}>
      {/* Fake header */}
      <div style={{
        background: '#2b2b2b', padding: '10px 14px',
        display: 'flex', alignItems: 'center', gap: 10,
        borderBottom: '1px solid rgba(255,255,255,.07)',
      }}>
        <div style={{ fontSize: 18, color: '#2AABEE' }}>‹</div>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>{editTitle}</div>
      </div>
      {/* Avatar row */}
      <div style={{ display: 'flex', justifyContent: 'center', padding: '14px 0 10px' }}>
        <div style={{
          width: 60, height: 60, borderRadius: '50%',
          background: 'linear-gradient(135deg, #2AABEE, #1178B8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 26,
        }}>🦎</div>
      </div>
      {/* Fields */}
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
      {/* About field — highlighted */}
      <div style={{
        padding: '10px 14px',
        background: 'rgba(95,186,71,.1)',
        border: '1.5px solid rgba(95,186,71,.5)',
        borderRadius: 8, margin: '6px 8px 8px',
      }}>
        <div style={{ color: '#5fba47', fontSize: 11, marginBottom: 4, fontWeight: 700 }}>{label}</div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <code style={{ color: '#fff', fontSize: 14, fontWeight: 700 }}>@LEMUR_SHOP</code>
          <span style={{ color: '#5fba47', fontSize: 11, fontWeight: 700 }}>{hint}</span>
        </div>
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

  useEffect(() => {
    bioPromoApi.status().then(setPromo).catch(() => {})
  }, [])

  async function doCheck() {
    setLoading(true); setMsg('')
    try {
      const res = await bioPromoApi.check()
      setPromo(res)
      if (res.rewarded)                             setMsg(T.bio_promo_rewarded)
      else if (!res.is_active)                      setMsg(T.bio_promo_not_active)
      else if ((res.hours_until_next ?? 0) > 0)     setMsg(T.bio_promo_wait(res.hours_until_next!))
      else                                          setMsg(T.bio_promo_ok)
    } catch { setMsg(T.bio_promo_error) }
    setLoading(false)
  }

  function close() { setOpen(false); setMsg('') }

  const active = promo?.is_active

  return (
    <>
      {/* Inline button — 2x bigger */}
      <button
        onClick={() => setOpen(true)}
        style={{
          background: active
            ? 'linear-gradient(135deg, rgba(95,186,71,.25), rgba(50,140,30,.15))'
            : 'rgba(255,255,255,.06)',
          border: active ? '1.5px solid rgba(95,186,71,.55)' : '1.5px solid rgba(255,255,255,.14)',
          borderRadius: 14, padding: '10px 16px', cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
          boxShadow: active ? '0 0 14px rgba(95,186,71,.2)' : 'none',
        }}>
        <span style={{ fontSize: 20, fontWeight: 900, lineHeight: 1, color: active ? '#5fba47' : 'var(--orange)' }}>+1⭐</span>
        <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 600, whiteSpace: 'nowrap' }}>{T.bio_promo_daily}</span>
        <span style={{ fontSize: 9, color: active ? 'rgba(95,186,71,.7)' : 'rgba(255,255,255,.3)', fontWeight: 600, whiteSpace: 'nowrap' }}>{T.bio_promo_daily_sub}</span>
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
            padding: '20px 20px 36px',
            maxHeight: '90vh', overflowY: 'auto',
          }}>
            <div style={{ width: 40, height: 4, borderRadius: 4, background: 'rgba(255,255,255,.15)', margin: '0 auto 20px' }} />
            <div style={{ fontWeight: 800, fontSize: 18, textAlign: 'center', marginBottom: 6 }}>{T.bio_promo_title}</div>
            <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', marginBottom: 16, lineHeight: 1.5 }}>
              {T.bio_promo_desc}
            </div>

            {/* Copyable card */}
            <div style={{
              background: 'rgba(95,186,71,.08)', border: '1.5px dashed rgba(95,186,71,.4)',
              borderRadius: 14, padding: '14px 16px', marginBottom: 14,
            }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6, letterSpacing: .5 }}>{T.bio_promo_add_label}</div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                <code style={{
                  fontSize: 18, fontWeight: 800, color: '#5fba47', letterSpacing: .5,
                  background: 'rgba(95,186,71,.12)', borderRadius: 8, padding: '6px 10px', flex: 1, textAlign: 'center',
                }}>@LEMUR_SHOP</code>
                <button
                  onClick={() => { navigator.clipboard?.writeText('@LEMUR_SHOP'); setMsg('📋 ' + T.copied) }}
                  style={{
                    background: 'rgba(95,186,71,.2)', border: '1px solid rgba(95,186,71,.4)',
                    borderRadius: 10, padding: '8px 12px', cursor: 'pointer', color: '#5fba47',
                    fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap', flexShrink: 0,
                  }}>{T.copy}</button>
              </div>
            </div>

            {/* Telegram UI mockup */}
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, letterSpacing: .5 }}>{T.bio_promo_how_label}</div>
            <TgProfileMockup lang={lang} />

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
                background: promo.is_active ? 'rgba(95,186,71,.1)' : 'rgba(255,80,80,.08)',
                border: `1px solid ${promo.is_active ? 'rgba(95,186,71,.3)' : 'rgba(255,80,80,.25)'}`,
                borderRadius: 14, padding: '12px 14px', marginBottom: 14,
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>
                    {promo.is_active ? T.bio_promo_active : T.bio_promo_inactive}
                  </div>
                  {promo.hours_until_next !== null && promo.hours_until_next > 0 && (
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
              {loading ? T.bio_promo_checking : promo?.joined ? T.bio_promo_recheck : T.bio_promo_check_btn}
            </button>
          </div>
        </div>
      )}
    </>
  )
}
