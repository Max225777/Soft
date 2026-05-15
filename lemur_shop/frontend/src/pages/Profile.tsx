import { type Me } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { me: Me | null; lang: Lang }

const LANG_LABELS: Record<string, string> = {
  ru: '🇷🇺 Русский',
  ua: '🇺🇦 Українська',
  en: '🇬🇧 English',
}

export default function Profile({ me, lang }: Props) {
  const T = getT(lang)
  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

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
            <span className="badge badge-orange">{LANG_LABELS[me.lang] ?? me.lang}</span>
          </div>
        </div>
      </div>

      <div className="card" style={{ textAlign: 'center' }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{T.orders}</div>
        <div style={{ fontWeight: 700, fontSize: 28, color: 'var(--orange)' }}>
          {me.orders_count}
        </div>
      </div>

      {me.is_admin && (
        <div className="card" style={{ background: 'var(--sand)', textAlign: 'center' }}>
          <span>⚙️ Admin</span>
        </div>
      )}
    </div>
  )
}
