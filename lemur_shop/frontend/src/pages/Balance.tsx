import { type Me } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { me: Me | null; lang: Lang }

export default function Balance({ me, lang }: Props) {
  const T = getT(lang)
  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

  const localBalance = lang === 'ua'
    ? `~${me.balance_uah.toLocaleString()} ₴`
    : lang === 'ru'
    ? `~${me.balance_rub.toLocaleString()} ₽`
    : null

  return (
    <div className="page">
      <h1>💰 {T.balance}</h1>

      <div className="card" style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ fontWeight: 700, fontSize: 36, color: 'var(--green)' }}>
          ${me.balance_usd.toFixed(2)}
        </div>
        {localBalance && (
          <div className="muted" style={{ fontSize: 14, marginTop: 4 }}>{localBalance}</div>
        )}
      </div>

      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 8 }}>💳 {T.topup}</div>
        <div className="muted" style={{ fontSize: 14 }}>{T.topup_info}</div>
      </div>
    </div>
  )
}
