import { useState, useEffect } from 'react'
import { api, type Referral } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang; botUsername: string }

export default function ReferralPage({ lang, botUsername }: Props) {
  const T = getT(lang)
  const [data, setData]     = useState<Referral | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => { api.referral().then(setData).catch(() => {}) }, [])

  if (!data) return <div className="page"><p className="muted">{T.loading}</p></div>

  const link = `https://t.me/${botUsername}?start=${data.referral_code}`

  function copy() {
    navigator.clipboard.writeText(link).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="page">
      <div style={{ fontWeight: 800, fontSize: 22, marginBottom: 6 }}>{T.referral}</div>
      <p className="muted" style={{ fontSize: 13, marginBottom: 18 }}>{T.ref_how}</p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 16 }}>
        <div className="card" style={{ textAlign: 'center', padding: '12px 8px' }}>
          <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>{T.ref_joined}</div>
          <div style={{ fontWeight: 800, fontSize: 26, color: 'var(--orange)' }}>{data.ref_count}</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '12px 8px' }}>
          <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>{T.ref_buyers}</div>
          <div style={{ fontWeight: 800, fontSize: 26, color: 'var(--orange)' }}>{data.buyers_count}</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '12px 8px' }}>
          <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>{T.ref_earned}</div>
          <div style={{ fontWeight: 800, fontSize: 22, color: '#FFD700' }}>⭐{data.earned_stars}</div>
        </div>
      </div>

      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{T.ref_link}</div>
        <div style={{
          background: 'rgba(255,255,255,.05)', border: '1px solid var(--border)',
          borderRadius: 10, padding: '10px 12px', fontSize: 12,
          wordBreak: 'break-all', marginBottom: 10, color: 'var(--text2)',
        }}>
          {link}
        </div>
        <button className="btn btn-primary" onClick={copy} style={{ fontSize: 14 }}>
          {copied ? T.ref_copied : T.ref_copy}
        </button>
      </div>
    </div>
  )
}
