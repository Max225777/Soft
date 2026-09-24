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
  const perBuyer  = lang === 'ru' ? 'за каждого приведённого друга, который купит TG-аккаунт' : lang === 'ua' ? 'за кожного приведеного друга, який купить TG-акаунт' : 'for every friend you bring who buys a TG account'
  const heroTitle = lang === 'ru' ? 'Приглашай друзей' : lang === 'ua' ? 'Запрошуй друзів' : 'Invite friends'
  const heroSub   = lang === 'ru' ? 'Делись ссылкой и получай ⭐ за покупки друзей' : lang === 'ua' ? 'Ділись посиланням і отримуй ⭐ за покупки друзів' : 'Share your link and earn ⭐ from friends’ purchases'
  const shareLbl  = lang === 'ru' ? '📤 Поделиться' : lang === 'ua' ? '📤 Поділитися' : '📤 Share'
  const shareText = lang === 'ru' ? 'Дешёвые Telegram-аккаунты и накрутка 🦎' : lang === 'ua' ? 'Дешеві Telegram-акаунти та накрутка 🦎' : 'Cheap Telegram accounts & boosting 🦎'

  function share() {
    const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(shareText)}`
    if (window.Telegram?.WebApp?.openTelegramLink) window.Telegram.WebApp.openTelegramLink(url)
    else window.open(url, '_blank')
  }

  return (
    <div className="page" style={{ paddingTop: 12 }}>

      {/* Hero */}
      <div style={{
        background: 'radial-gradient(120% 100% at 20% 0%, rgba(255,184,48,.16) 0%, transparent 55%), var(--card)',
        border: '1px solid rgba(255,184,48,.25)',
        borderRadius: 20, padding: '18px 18px', marginBottom: 14,
        display: 'flex', alignItems: 'center', gap: 14, position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          width: 52, height: 52, borderRadius: 16, flexShrink: 0,
          background: 'linear-gradient(135deg, #FFD700, #e0a000)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26,
          boxShadow: '0 4px 14px rgba(255,184,48,.4)',
        }}>🤝</div>
        <div>
          <div style={{ fontWeight: 800, fontSize: 18 }}>{heroTitle}</div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2, lineHeight: 1.4 }}>{heroSub}</div>
        </div>
      </div>

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
        <button className="btn btn-primary" onClick={copy} style={{ fontSize: 14, flex: 1 }}>
          {copied ? T.ref_copied : T.ref_copy}
        </button>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn" onClick={share} style={{
            width: '100%', fontSize: 14, background: 'linear-gradient(135deg,#2AABEE,#1c8fd0)', color: '#fff',
          }}>{shareLbl}</button>
        </div>
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
      background: r.is_buyer ? 'rgba(46,124,246,.12)' : 'rgba(255,255,255,.04)',
      border: `1px solid ${r.is_buyer ? 'rgba(46,124,246,.35)' : 'var(--border)'}`,
    }}>
      <div>
        <span style={{ fontWeight: 600, fontSize: 14, color: r.is_buyer ? '#7DB4FF' : 'var(--text)' }}>
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
