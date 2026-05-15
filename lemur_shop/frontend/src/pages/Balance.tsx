import { type Me } from '../api'
import { getT, type Lang } from '../i18n'
import { getLevel, getLevelIdx, LEVELS } from './Profile'

interface Props { me: Me | null; lang: Lang }

export default function Balance({ me, lang }: Props) {
  const T = getT(lang)
  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

  const usd = me.balance_usd
  const spent = me.total_spent_usd ?? 0
  const lvl = getLevel(spent)
  const lvlIdx = getLevelIdx(spent)

  const balanceLocal = lang === 'ua' && me.rate_uah
    ? { main: `${Math.round(usd * me.rate_uah)}₴`, sub: `$${usd.toFixed(2)}` }
    : lang === 'ru' && me.rate_rub
    ? { main: `${Math.round(usd * me.rate_rub)}₽`, sub: `$${usd.toFixed(2)}` }
    : { main: `$${usd.toFixed(2)}`, sub: null }

  return (
    <div className="page">
      <h1 style={{ marginBottom: 16 }}>{T.balance}</h1>

      {/* Balance hero card */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20,
        padding: '24px 20px',
        marginBottom: 10,
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -40, right: -40,
          width: 180, height: 180, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,107,43,.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 8 }}>
          {T.balance.toUpperCase()}
        </div>

        <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1, marginBottom: balanceLocal.sub ? 6 : 16 }}>
          <span style={{ fontWeight: 800, fontSize: 42 }}>{balanceLocal.main}</span>
        </div>
        {balanceLocal.sub && (
          <div style={{ fontSize: 16, color: 'var(--muted)', fontWeight: 400, marginBottom: 16 }}>{balanceLocal.sub}</div>
        )}

        {/* Level badge inside hero */}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: `${lvl.color}15`, border: `1px solid ${lvl.color}30`,
          borderRadius: 20, padding: '6px 14px',
        }}>
          <span style={{ fontSize: 16 }}>{lvl.icon}</span>
          <span style={{ fontWeight: 700, fontSize: 13, color: lvl.color }}>{lvl.name[lang]}</span>
          <span style={{
            fontSize: 11, fontWeight: 700, padding: '1px 7px', borderRadius: 20,
            background: `${lvl.color}25`, color: lvl.color,
          }}>−{lvl.discount}%</span>
        </div>
      </div>

      {/* Level dots row */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
          {lang === 'ua' ? 'Рівень знижки' : lang === 'ru' ? 'Уровень скидки' : 'Discount level'}
        </div>
        <div style={{ display: 'flex', gap: 5, marginBottom: 14 }}>
          {LEVELS.map((l, i) => (
            <div key={i} style={{ flex: 1, textAlign: 'center' }}>
              <div style={{
                height: 3, borderRadius: 3, marginBottom: 5,
                background: i <= lvlIdx ? l.color : 'rgba(255,255,255,.08)',
                boxShadow: i <= lvlIdx ? `0 0 6px ${l.glow}` : 'none',
              }} />
              <div style={{ fontSize: 18 }}>{l.icon}</div>
              <div style={{ fontSize: 10, fontWeight: 700, color: i === lvlIdx ? l.color : 'var(--muted)', marginTop: 3 }}>
                −{l.discount}%
              </div>
              <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>
                ${l.min}+
              </div>
            </div>
          ))}
        </div>
        <div style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(255,184,48,.06)', border: '1px solid rgba(255,184,48,.15)' }}>
          <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.6 }}>
            💡 {T.level_info}
          </div>
        </div>
      </div>

      {/* Top up */}
      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 8 }}>💳 {T.topup}</div>
        <div className="muted" style={{ fontSize: 14 }}>{T.topup_info}</div>
      </div>
    </div>
  )
}
