import { useState, useEffect } from 'react'
import { bioPromoApi, type BioPromoStatus } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang }

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

  return (
    <>
      {/* Inline button */}
      <button
        onClick={() => setOpen(true)}
        style={{
          background: promo?.is_active
            ? 'linear-gradient(135deg, rgba(95,186,71,.2), rgba(50,140,30,.1))'
            : 'rgba(255,255,255,.06)',
          border: promo?.is_active ? '1px solid rgba(95,186,71,.45)' : '1px solid rgba(255,255,255,.12)',
          borderRadius: 12, padding: '7px 11px', cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1,
        }}>
        <span style={{ fontSize: 13, fontWeight: 800, color: promo?.is_active ? '#5fba47' : 'var(--orange)' }}>+1⭐</span>
        <span style={{ fontSize: 9, color: 'var(--muted)', fontWeight: 600 }}>{T.bio_promo_daily}</span>
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

            {/* Steps */}
            <div style={{
              background: 'rgba(255,255,255,.03)', border: '1px solid var(--border)',
              borderRadius: 14, padding: '12px 14px', marginBottom: 14,
            }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, letterSpacing: .5 }}>{T.bio_promo_how_label}</div>
              {([
                ['1', T.bio_promo_step1],
                ['2', T.bio_promo_step2],
                ['3', T.bio_promo_step3],
              ] as [string, string][]).map(([n, t]) => (
                <div key={n} style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: n === '3' ? 0 : 6 }}>
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
