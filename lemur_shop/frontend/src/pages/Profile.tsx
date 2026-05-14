import { type Me } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { me: Me | null; lang: Lang }

export default function Profile({ me, lang }: Props) {
  const T = getT(lang)
  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

  const balanceLocal = lang === 'ua'
    ? `~${me.balance_uah.toLocaleString()} ₴`
    : `~${me.balance_rub.toLocaleString()} ₽`

  return (
    <div className="page">
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%',
          background: 'var(--orange)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 24, fontWeight: 700, flexShrink: 0,
        }}>
          {me.name.charAt(0).toUpperCase()}
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 17 }}>{me.name}</div>
          {me.username && <div className="muted">@{me.username}</div>}
          <div style={{ marginTop: 4 }}>
            <span className="badge badge-orange">
              {lang === 'ua' ? '🇺🇦 Українська' : '🇷🇺 Русский'}
            </span>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{T.balance}</div>
          <div style={{ fontWeight: 700, fontSize: 18, color: 'var(--green)' }}>
            ${me.balance_usd.toFixed(2)}
          </div>
          <div className="muted" style={{ fontSize: 12 }}>{balanceLocal}</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{T.orders}</div>
          <div style={{ fontWeight: 700, fontSize: 28, color: 'var(--orange)' }}>
            {me.orders_count}
          </div>
        </div>
      </div>

      {me.is_admin && (
        <div className="card" style={{ background: 'var(--sand)', textAlign: 'center' }}>
          <span>⚙️ Адмін</span>
        </div>
      )}
    </div>
  )
}
