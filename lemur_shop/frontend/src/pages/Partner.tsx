import { useState, useEffect } from 'react'
import { api, type PartnerData, type Me } from '../api'
import type { Lang } from '../i18n'

interface Props { lang: Lang; me: Me | null }

export default function Partner({ lang }: Props) {
  const [data, setData] = useState<PartnerData | null>(null)
  const [loading, setLoading] = useState(true)
  const [newTitle, setNewTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [withdrawing, setWithdrawing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const [refSort, setRefSort] = useState<'earned' | 'time'>('earned')
  const [apiKey, setApiKey] = useState<string | null | undefined>(undefined)
  const [apiBusy, setApiBusy] = useState(false)
  const [apiRevealed, setApiRevealed] = useState(false)

  useEffect(() => { api.partnerApiKey().then(r => setApiKey(r.api_key)).catch(() => setApiKey(null)) }, [])

  async function genApiKey() {
    if (apiBusy) return
    setApiBusy(true)
    try {
      const r = await api.partnerApiKeyRegen()
      setApiKey(r.api_key)
      setApiRevealed(true)
    } catch { /* ignore */ }
    finally { setApiBusy(false) }
  }

  function load() {
    api.partner().then(setData).catch(() => {}).finally(() => setLoading(false))
  }
  useEffect(load, [])

  function copy(text: string, key: string) {
    try {
      navigator.clipboard?.writeText(text)
    } catch { /* ignore */ }
    setCopied(key)
    setTimeout(() => setCopied(null), 1500)
  }

  async function createLink() {
    if (creating) return
    setCreating(true); setMsg(null)
    try {
      await api.partnerCreateLink(newTitle.trim())
      setNewTitle('')
      load()
    } catch (e: any) {
      setMsg(e?.message === 'too_many_links' ? 'Достигнут лимит ссылок (20)' : 'Ошибка создания ссылки')
    } finally { setCreating(false) }
  }

  async function withdraw() {
    if (withdrawing || !data) return
    setWithdrawing(true); setMsg(null)
    try {
      const r = await api.partnerWithdraw()
      setMsg(`Заявка на вывод $${r.amount_usd.toFixed(2)} отправлена ✅`)
      load()
    } catch (e: any) {
      const m = e?.message === 'below_min' ? `Минимум для вывода — $${data.min_withdraw_usd.toFixed(2)}`
        : e?.message === 'already_requested' ? 'Заявка уже создана, дождитесь выплаты'
        : 'Ошибка вывода'
      setMsg(m)
    } finally { setWithdrawing(false) }
  }

  const L = {
    ru: { title: 'Партнёрка', bal: 'Партнёрский баланс', earned: 'Всего заработано', invited: 'Приглашено',
      how: 'КАК ЭТО РАБОТАЕТ', links: 'МОИ ССЫЛКИ', create: 'Создать ссылку', ph: 'Название (напр. Instagram)',
      withdraw: 'Вывести', recent: 'ПОСЛЕДНИЕ НАЧИСЛЕНИЯ', empty: 'Пока нет ссылок — создайте первую',
      copy: 'Копировать', copied: 'Скопировано', paid: 'Выплачено', pending: 'Заявка на вывод в обработке',
      inv: 'приглашено', ern: 'заработано', first: 'первая покупка', next: 'покупка' },
  }.ru

  if (loading) return <div className="page" style={{ textAlign: 'center', paddingTop: 60, color: 'var(--muted)' }}>⏳</div>
  if (!data) return <div className="page" style={{ textAlign: 'center', paddingTop: 60, color: 'var(--muted)' }}>Нет данных</div>

  return (
    <div className="page">
      <h1 style={{ marginBottom: 14, fontSize: 20 }}>🤝 {L.title}</h1>

      {/* Balance hero */}
      <div style={{
        background: 'linear-gradient(135deg, #12251c 0%, #0d1a14 100%)',
        border: '1px solid rgba(74,222,128,.28)', borderRadius: 20, padding: '18px 18px', marginBottom: 12,
      }}>
        <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: 1, marginBottom: 4 }}>{L.bal.toUpperCase()}</div>
        <div style={{ color: '#4ade80', fontWeight: 800, fontSize: 30, lineHeight: 1 }}>${data.balance_usd.toFixed(2)}</div>
        <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
          <div><div style={{ fontSize: 11, color: 'var(--muted)' }}>{L.earned}</div><div style={{ fontWeight: 700 }}>${data.total_earned_usd.toFixed(2)}</div></div>
          <div><div style={{ fontSize: 11, color: 'var(--muted)' }}>{L.invited}</div><div style={{ fontWeight: 700 }}>{data.total_invited}</div></div>
          <div><div style={{ fontSize: 11, color: 'var(--muted)' }}>{L.paid}</div><div style={{ fontWeight: 700 }}>${data.paid_usd.toFixed(2)}</div></div>
        </div>
        <button
          onClick={withdraw}
          disabled={withdrawing || data.has_pending_payout || data.balance_usd < data.min_withdraw_usd}
          className="btn"
          style={{
            width: '100%', marginTop: 14, padding: '12px', fontSize: 14, fontWeight: 800,
            background: data.balance_usd >= data.min_withdraw_usd && !data.has_pending_payout
              ? 'linear-gradient(135deg, #4ade80, #22a55a)' : 'rgba(255,255,255,.08)',
            color: data.balance_usd >= data.min_withdraw_usd && !data.has_pending_payout ? '#0d1a14' : 'var(--muted)',
          }}
        >
          {data.has_pending_payout ? '⏳ ' + L.pending : withdrawing ? '⏳...' : `💸 ${L.withdraw} ($${data.balance_usd.toFixed(2)})`}
        </button>
      </div>

      {msg && <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12, textAlign: 'center' }}>{msg}</div>}

      {/* How it works */}
      <div style={{
        background: 'rgba(74,222,128,.06)', border: '1px solid rgba(74,222,128,.18)',
        borderRadius: 14, padding: '12px 14px', marginBottom: 16, fontSize: 13, color: 'var(--text2)', lineHeight: 1.55,
      }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8, marginBottom: 6 }}>{L.how}</div>
        Приглашай людей по своей ссылке. На каждого приглашённого включается таймер <b>{data.window_days} дней</b>: всё это время ты получаешь <b>{data.pct}%</b> чистой прибыли со <b>всех</b> его покупок TG-аккаунтов (не только с первой). После окончания таймера начисления по этому рефералу прекращаются. Вывод — по кнопке выше.
      </div>

      {/* Links */}
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8, marginBottom: 8 }}>{L.links}</div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          value={newTitle}
          onChange={e => setNewTitle(e.target.value)}
          placeholder={L.ph}
          style={{
            flex: 1, padding: '10px 12px', borderRadius: 11, fontSize: 14,
            background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text)',
          }}
        />
        <button onClick={createLink} disabled={creating} className="btn btn-primary" style={{ width: 'auto', padding: '10px 16px', fontSize: 14, fontWeight: 700 }}>
          {creating ? '⏳' : '＋'}
        </button>
      </div>

      {data.links.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center', padding: '10px 0 16px' }}>{L.empty}</div>
      )}

      {data.links.map(lk => (
        <div key={lk.id} style={{
          background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 14,
          padding: '12px 14px', marginBottom: 8,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <div style={{ fontWeight: 700, fontSize: 14 }}>{lk.title}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>{lk.invited} {L.inv} · <span style={{ color: '#4ade80' }}>${lk.earned_usd.toFixed(2)}</span></div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <code style={{ flex: 1, fontSize: 12, color: 'var(--text2)', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>{lk.url}</code>
            <button onClick={() => copy(lk.url, `l${lk.id}`)} className="btn btn-secondary" style={{ width: 'auto', padding: '6px 12px', fontSize: 12 }}>
              {copied === `l${lk.id}` ? L.copied : L.copy}
            </button>
          </div>
        </div>
      ))}

      {/* Referrals list with filter */}
      {data.referrals.length > 0 && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '16px 0 8px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8 }}>МОИ РЕФЕРАЛЫ ({data.referrals.length})</div>
            <div style={{ display: 'flex', gap: 4 }}>
              {(['earned', 'time'] as const).map(m => (
                <button key={m} onClick={() => setRefSort(m)} style={{
                  padding: '4px 9px', fontSize: 11, borderRadius: 8, cursor: 'pointer',
                  background: refSort === m ? 'rgba(74,222,128,.15)' : 'transparent',
                  color: refSort === m ? '#4ade80' : 'var(--muted)',
                  border: refSort === m ? '1px solid rgba(74,222,128,.35)' : '1px solid var(--border)',
                }}>{m === 'earned' ? '💰 по доходу' : '⏳ по времени'}</button>
              ))}
            </div>
          </div>
          {[...data.referrals].sort((a, b) => refSort === 'earned'
            ? b.earned_usd - a.earned_usd
            : b.days_left - a.days_left).map((r, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '9px 12px', borderRadius: 11, marginBottom: 5,
              background: r.active ? 'rgba(74,222,128,.05)' : 'rgba(255,255,255,.03)',
              border: `1px solid ${r.active ? 'rgba(74,222,128,.12)' : 'var(--border)'}`,
            }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>{r.name}</div>
                <div style={{ fontSize: 11, color: r.active ? '#4ade80' : 'var(--muted)' }}>
                  {r.active ? `⏳ осталось ${r.days_left} дн.` : '⛔ таймер истёк'}
                </div>
              </div>
              <div style={{ fontWeight: 800, color: '#4ade80', fontSize: 13, flexShrink: 0 }}>${r.earned_usd.toFixed(2)}</div>
            </div>
          ))}
        </>
      )}

      {/* Recent earnings */}
      {data.recent.length > 0 && (
        <>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8, margin: '16px 0 8px' }}>{L.recent}</div>
          {data.recent.map((r, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 12px', borderRadius: 11, marginBottom: 5,
              background: 'rgba(74,222,128,.05)', border: '1px solid rgba(74,222,128,.12)',
            }}>
              <div style={{ fontSize: 12, color: 'var(--text2)' }}>
                🛍 покупка реферала
                {r.created_at && <span style={{ color: 'var(--muted)', marginLeft: 8 }}>{new Date(r.created_at).toLocaleDateString('ru', { day: 'numeric', month: 'short' })}</span>}
              </div>
              <div style={{ fontWeight: 800, color: '#4ade80', fontSize: 13 }}>+${r.amount_usd.toFixed(2)}</div>
            </div>
          ))}
        </>
      )}

      {/* ── API для разработчиков ── */}
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)', letterSpacing: .8, margin: '20px 0 8px' }}>API ДЛЯ РАЗРАБОТЧИКОВ</div>
      <div style={{
        background: 'radial-gradient(130% 100% at 12% 0%, rgba(46,124,246,.14) 0%, transparent 55%), var(--card)',
        border: '1px solid rgba(46,124,246,.28)', borderRadius: 16, padding: '14px 16px',
      }}>
        <div style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.5, marginBottom: 12 }}>
          Покупайте TG-аккаунты программно по API-ключу. Покупки через API <b>не начисляют</b> партнёрскую комиссию и рефбонусы.
        </div>

        {apiKey === undefined ? (
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>⏳ ...</div>
        ) : apiKey ? (
          <>
            <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: .5, marginBottom: 6 }}>ВАШ КЛЮЧ</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <code style={{
                flex: 1, fontSize: 12, color: '#7DB4FF', overflow: 'hidden',
                whiteSpace: 'nowrap', textOverflow: 'ellipsis', background: 'var(--bg2)',
                border: '1px solid var(--border)', borderRadius: 10, padding: '10px 12px',
              }}>{apiRevealed ? apiKey : 'lemur_' + '•'.repeat(18)}</code>
              <button onClick={() => setApiRevealed(v => !v)} className="btn btn-secondary" style={{ width: 'auto', padding: '9px 12px', fontSize: 12 }}>
                {apiRevealed ? '🙈' : '👁'}
              </button>
              <button onClick={() => { navigator.clipboard?.writeText(apiKey); setCopied('apikey'); setTimeout(() => setCopied(null), 1500) }}
                className="btn btn-secondary" style={{ width: 'auto', padding: '9px 12px', fontSize: 12 }}>
                {copied === 'apikey' ? '✓' : '📋'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <a href="/api-docs" target="_blank" rel="noreferrer" style={{ flex: 1, textDecoration: 'none' }}>
                <button className="btn btn-primary" style={{ width: '100%', fontSize: 13, padding: '11px' }}>📖 Документация</button>
              </a>
              <button onClick={genApiKey} disabled={apiBusy} className="btn btn-secondary" style={{ width: 'auto', padding: '11px 14px', fontSize: 13 }}>
                {apiBusy ? '⏳' : '↻ Сбросить'}
              </button>
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 8, lineHeight: 1.4 }}>
              «Сбросить» создаст новый ключ, старый перестанет работать.
            </div>
          </>
        ) : (
          <>
            <button onClick={genApiKey} disabled={apiBusy} className="btn btn-primary" style={{ width: '100%', fontSize: 14, padding: '12px' }}>
              {apiBusy ? '⏳ ...' : '🔑 Сгенерировать API-ключ'}
            </button>
            <a href="/api-docs" target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
              <div style={{ textAlign: 'center', fontSize: 12, color: '#7DB4FF', marginTop: 10 }}>📖 Открыть документацию</div>
            </a>
          </>
        )}
      </div>
    </div>
  )
}
