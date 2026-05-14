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
      <h1>👥 {T.referral.replace(/^[^ ]+ /, '')}</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        {T.ref_bonus}: <strong>+{data.bonus_pct}%</strong>
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{T.ref_count}</div>
          <div style={{ fontWeight: 700, fontSize: 28, color: 'var(--orange)' }}>{data.ref_count}</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{T.ref_earned}</div>
          <div style={{ fontWeight: 700, fontSize: 18, color: 'var(--green)' }}>
            ${data.earned_usd.toFixed(2)}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="muted" style={{ marginBottom: 8 }}>{T.ref_link}</div>
        <div style={{
          background: 'var(--sand)', borderRadius: 8, padding: '10px 12px',
          fontSize: 13, wordBreak: 'break-all', marginBottom: 10,
          color: 'var(--brown2)',
        }}>
          {link}
        </div>
        <button className="btn btn-primary" onClick={copy}>
          {copied ? T.copied : T.copy}
        </button>
      </div>
    </div>
  )
}
