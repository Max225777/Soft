import { useState, useEffect } from 'react'
import { api, type Me, type LeaderRow } from '../api'
import { getT, type Lang } from '../i18n'
import LegalFooter from '../components/LegalFooter'

interface Props { me: Me | null; lang: Lang; onChangeLang: (l: Lang) => void }

const LANG_LABELS: Record<string, string> = {
  ru: '🇷🇺 Русский',
  ua: '🇺🇦 Українська',
  en: '🇬🇧 English',
}
const LANG_KEY = 'lemur_lang'

const MEDALS = ['🥇', '🥈', '🥉']

export default function Profile({ me, lang, onChangeLang }: Props) {
  const T = getT(lang)
  const [leaders, setLeaders] = useState<LeaderRow[]>([])
  const [loadingLeaders, setLoadingLeaders] = useState(true)
  const [period, setPeriod] = useState<'all' | 'today'>('all')

  useEffect(() => {
    setLoadingLeaders(true)
    api.leaderboard(period).then(r => { setLeaders(r); setLoadingLeaders(false) }).catch(() => setLoadingLeaders(false))
  }, [period])

  function changeLang(l: Lang) {
    localStorage.setItem(LANG_KEY, l)
    api.setLang(l).catch(() => {})
    onChangeLang(l)
  }

  if (!me) return <div className="page"><p className="muted">{T.loading}</p></div>

  const starsBalance = me.balance_stars
  const usdDisplay = (starsBalance * 0.013).toFixed(2)

  return (
    <div className="page">

      {/* ── Hero card ── */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #1A1020 50%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20,
        padding: '22px 18px 20px',
        marginBottom: 10,
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -40, right: -40,
          width: 180, height: 180, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,107,43,.15) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 16,
            background: 'rgba(255,107,43,.2)',
            border: '1.5px solid rgba(255,107,43,.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22, fontWeight: 800, color: '#fff', flexShrink: 0,
          }}>
            {me.name.charAt(0).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 17 }}>{me.name}</div>
            {me.username && <div className="muted" style={{ fontSize: 13, marginTop: 1 }}>@{me.username}</div>}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--muted)', letterSpacing: 1, marginBottom: 6 }}>
            {T.balance.toUpperCase()}
          </div>
          <div className="balance-glow" style={{ color: 'var(--orange)', lineHeight: 1 }}>
            <span style={{ fontWeight: 800, fontSize: 38 }}>⭐{starsBalance}</span>
            <span style={{ fontWeight: 400, fontSize: 18, marginLeft: 10, color: 'var(--muted)' }}>(${usdDisplay})</span>
          </div>
        </div>
      </div>

      {/* ── Socials ── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 0 }}>
        <a href="https://t.me/LEMUR_SHOP" target="_blank" rel="noreferrer" style={{ flex: 1, textDecoration: 'none', minWidth: 0 }}>
          <div style={{
            background: 'linear-gradient(135deg, rgba(42,171,238,.12), rgba(17,120,184,.06))',
            border: '1px solid rgba(42,171,238,.22)',
            borderRadius: 14, padding: '12px 10px',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <div style={{ width: 30, height: 30, borderRadius: 9, flexShrink: 0, background: 'linear-gradient(135deg, #2AABEE, #1178B8)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>📢</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 12, color: '#2AABEE', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>@LEMUR_SHOP</div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
                {lang === 'ua' ? 'Канал' : 'Канал'}
              </div>
            </div>
          </div>
        </a>
        <a href="https://t.me/LEMUR_MANEGER" target="_blank" rel="noreferrer" style={{ flex: 1, textDecoration: 'none', minWidth: 0 }}>
          <div style={{
            background: 'linear-gradient(135deg, rgba(76,175,114,.1), rgba(76,175,114,.04))',
            border: '1px solid rgba(76,175,114,.22)',
            borderRadius: 14, padding: '12px 10px',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <div style={{ width: 30, height: 30, borderRadius: 9, flexShrink: 0, background: 'linear-gradient(135deg, #4CAF72, #2e7a4e)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>💬</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 12, color: '#4CAF72', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>@LEMUR_MANEGER</div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
                {lang === 'ua' ? 'Підтримка' : 'Поддержка'}
              </div>
            </div>
          </div>
        </a>
      </div>

      {/* ── Language ── */}
      <div className="card" style={{ marginTop: 10 }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{T.change_lang}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['ru', 'ua', 'en'] as Lang[]).map(l => (
            <button
              key={l}
              className={`btn ${lang === l ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, padding: '9px 4px', fontSize: 13 }}
              onClick={() => changeLang(l)}
            >
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
      </div>

      {/* ── Leaderboard ── */}
      <div style={{ fontWeight: 800, fontSize: 16, margin: '18px 0 10px' }}>
        🏆 {lang === 'ru' ? 'Таблица лидеров — по тратам' : lang === 'ua' ? 'Таблиця лідерів — за витратами' : 'Leaderboard — by spending'}
      </div>

      {/* Period switch */}
      <div style={{ display: 'flex', gap: 0, background: 'var(--bg2)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden', marginBottom: 10 }}>
        {(['all', 'today'] as const).map((p, i) => {
          const label = p === 'all'
            ? (lang === 'ru' ? 'За всё время' : lang === 'ua' ? 'За весь час' : 'All time')
            : (lang === 'ru' ? 'За сегодня' : lang === 'ua' ? 'За сьогодні' : 'Today')
          return (
            <button key={p} onClick={() => setPeriod(p)} style={{
              flex: 1, padding: '9px 6px', fontSize: 12, fontWeight: period === p ? 700 : 500,
              background: period === p ? 'rgba(255,107,43,.18)' : 'transparent',
              color: period === p ? 'var(--orange)' : 'var(--muted)',
              border: 'none', cursor: 'pointer',
              borderRight: i === 0 ? '1px solid var(--border)' : 'none',
            }}>{label}</button>
          )
        })}
      </div>

      {loadingLeaders ? (
        <div className="card"><div className="skeleton" style={{ height: 200 }} /></div>
      ) : leaders.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', color: 'var(--muted)', padding: '28px 16px' }}>
          {lang === 'ru' ? 'Нет данных' : lang === 'ua' ? 'Немає даних' : 'No data'}
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {leaders.map((row, i) => (
            <div key={row.rank} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '11px 14px',
              borderBottom: i < leaders.length - 1 ? '1px solid var(--border)' : 'none',
              background: row.is_me ? 'rgba(255,107,43,.07)' : 'transparent',
            }}>
              <div style={{ width: 28, textAlign: 'center', fontSize: i < 3 ? 18 : 13, fontWeight: 700, color: i < 3 ? undefined : 'var(--muted)', flexShrink: 0 }}>
                {i < 3 ? MEDALS[i] : `#${i + 1}`}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: row.is_me ? 800 : 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: row.is_me ? 'var(--orange)' : 'var(--text)' }}>
                  {row.name}{row.is_me ? ' 👈' : ''}
                </div>
                {row.username && <div className="muted" style={{ fontSize: 11, marginTop: 1 }}>@{row.username}</div>}
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 13 }}>⭐{row.total_stars.toLocaleString()}</div>
                <div className="muted" style={{ fontSize: 10, marginTop: 1 }}>{row.orders_count} замовл.</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {me.is_admin && (
        <div className="card" style={{ textAlign: 'center', marginTop: 8, border: '1px solid rgba(255,184,48,.25)', background: 'rgba(255,184,48,.06)' }}>
          <span style={{ color: 'var(--gold)', fontWeight: 700 }}>⚙️ Admin</span>
        </div>
      )}
      <LegalFooter />
    </div>
  )
}
