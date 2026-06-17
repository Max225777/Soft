import { useState, useEffect } from 'react'
import { api, type Referral, type ReferralUser } from '../api'
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

  const condTitle = lang === 'ru' ? 'Условия программы' : lang === 'ua' ? 'Умови програми' : 'Program conditions'
  const perBuyer  = lang === 'ru' ? 'за каждого приглашённого, который купит TG-аккаунт' : lang === 'ua' ? 'за кожного запрошеного, який купить TG-акаунт' : 'for each invited person who buys a TG account'

  return (
    <div className="page" style={{ paddingTop: 12 }}>

      {/* Умови */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(255,184,48,.08), rgba(255,184,48,.03))',
        border: '1px solid rgba(255,184,48,.25)',
        borderRadius: 16, padding: '16px', marginBottom: 16,
      }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: '#FFB830', marginBottom: 12 }}>
          🎁 {condTitle}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            background: 'rgba(255,184,48,.15)', border: '1px solid rgba(255,184,48,.3)',
            borderRadius: 14, padding: '10px 16px', textAlign: 'center', flexShrink: 0,
          }}>
            <div style={{ fontWeight: 900, fontSize: 28, color: '#FFD700', lineHeight: 1 }}>+25</div>
            <div style={{ fontWeight: 700, fontSize: 18, color: '#FFD700' }}>⭐</div>
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)', lineHeight: 1.4 }}>
              {perBuyer}
            </div>
          </div>
        </div>
      </div>

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

      <div className="card" style={{ marginBottom: 16 }}>
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

      {data.referrals.length > 0 && (
        <div className="card">
          <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{T.ref_list}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {data.referrals.map((r, i) => (
              <RefRow key={i} r={r} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function RefRow({ r }: { r: ReferralUser }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '8px 10px', borderRadius: 10,
      background: r.is_buyer ? 'rgba(255,107,43,.12)' : 'rgba(255,255,255,.04)',
      border: `1px solid ${r.is_buyer ? 'rgba(255,107,43,.35)' : 'var(--border)'}`,
    }}>
      <div>
        <span style={{ fontWeight: 600, fontSize: 14, color: r.is_buyer ? 'var(--orange)' : 'var(--text)' }}>
          {r.name}
        </span>
        {r.username && (
          <span className="muted" style={{ fontSize: 12, marginLeft: 6 }}>@{r.username}</span>
        )}
      </div>
      {r.is_buyer && (
        <span style={{ fontSize: 12, color: '#FFD700', fontWeight: 700 }}>⭐+25</span>
      )}
    </div>
  )
}
