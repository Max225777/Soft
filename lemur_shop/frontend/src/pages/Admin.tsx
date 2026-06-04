import { useState, useEffect, useCallback, useRef } from 'react'
import { adminApi, type AdminStats, type AdminUser, type AdminUserDetail, type AdminOrderRow, type AdminTopupRow, type BroadcastStatus } from '../api'

type DateMode = 'today' | 'all' | 'custom'

function useOverviewStats(dateFrom: string, dateTo: string) {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const reload = useCallback(() => {
    setLoading(true)
    adminApi.stats(dateFrom || undefined, dateTo || undefined).then(setStats).finally(() => setLoading(false))
  }, [dateFrom, dateTo])
  useEffect(() => { reload() }, [reload])
  return { stats, loading, reload }
}

type AdminTab = 'overview' | 'users' | 'orders' | 'topups' | 'broadcast'

const CATEGORY_FLAGS: Record<string, string> = { us: '🇺🇸', ua: '🇺🇦', kz: '🇰🇿' }

function fmt(dt: string) {
  return new Date(dt).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function StatCard({ label, value, sub, color = 'var(--orange)' }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 14, padding: '14px 16px', flex: 1, minWidth: 0,
    }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontWeight: 800, fontSize: 22, color }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function Pagination({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  if (pages <= 1) return null
  return (
    <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginTop: 12, flexWrap: 'wrap' }}>
      <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: 13 }}
        disabled={page <= 1} onClick={() => onPage(page - 1)}>←</button>
      <span style={{ alignSelf: 'center', fontSize: 13, color: 'var(--muted)' }}>{page} / {pages}</span>
      <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: 13 }}
        disabled={page >= pages} onClick={() => onPage(page + 1)}>→</button>
    </div>
  )
}

// ── Overview ──────────────────────────────────────────────────────────────────
function Overview() {
  const todayStr = new Date().toISOString().slice(0, 10)
  const [mode, setMode] = useState<DateMode>('today')
  const [customFrom, setCustomFrom] = useState(todayStr)
  const [customTo, setCustomTo]     = useState(todayStr)

  const dateFrom = mode === 'today' ? todayStr : mode === 'custom' ? customFrom : ''
  const dateTo   = mode === 'today' ? todayStr : mode === 'custom' ? customTo   : ''

  const { stats, loading, reload } = useOverviewStats(dateFrom, dateTo)
  const [resetting, setResetting] = useState(false)

  async function handleReset() {
    if (!confirm('Скинути ВСІ баланси, замовлення і поповнення? Це незворотно!')) return
    setResetting(true)
    try {
      await adminApi.resetStats()
      reload()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setResetting(false)
    }
  }

  const profitColor = (v: number) => v >= 0 ? '#4CAF72' : '#ff5555'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Date mode picker */}
      <div style={{ display: 'flex', gap: 6 }}>
        {(['today', 'all', 'custom'] as DateMode[]).map(m => (
          <button key={m} onClick={() => setMode(m)} style={{
            flex: 1, padding: '8px 4px', fontSize: 12, fontWeight: mode === m ? 700 : 500,
            background: mode === m ? 'rgba(255,107,43,.2)' : 'var(--bg2)',
            color: mode === m ? 'var(--orange)' : 'var(--muted)',
            border: mode === m ? '1px solid rgba(255,107,43,.4)' : '1px solid var(--border)',
            borderRadius: 10, cursor: 'pointer',
          }}>
            {m === 'today' ? '📅 Сьогодні' : m === 'all' ? '📊 Весь час' : '🗓 Дата'}
          </button>
        ))}
      </div>
      {mode === 'custom' && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)}
            style={{ flex: 1, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', color: 'var(--text)', fontSize: 13 }} />
          <span style={{ color: 'var(--muted)', fontSize: 13 }}>—</span>
          <input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)}
            style={{ flex: 1, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', color: 'var(--text)', fontSize: 13 }} />
        </div>
      )}

      {loading && <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)' }}>⏳ Завантаження...</div>}
      {!loading && !stats && <div style={{ padding: 20, color: 'var(--red)' }}>Помилка завантаження</div>}
      {!loading && stats && (<>

        {/* Today always shown */}
        {mode !== 'custom' && (<>
          <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--muted)', marginBottom: -4 }}>СЬОГОДНІ</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <StatCard label="Нових юзерів" value={stats.new_users_today} color="#4CAF72" />
            <StatCard label="Замовлень" value={stats.orders_today} color="var(--orange)" />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <StatCard label="Дохід сьогодні" value={`$${stats.revenue_today.toFixed(2)}`} color="var(--orange)"
              sub={`⭐${Math.round(stats.revenue_today / 0.013)}`} />
            <StatCard label="Прибуток сьогодні" value={`$${stats.profit_today.toFixed(2)}`}
              color={profitColor(stats.profit_today)} sub={`витрати $${stats.cost_today.toFixed(2)}`} />
          </div>
        </>)}

        {/* Period stats */}
        <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--muted)', marginTop: 4, marginBottom: -4 }}>
          {mode === 'today' ? 'ЗАГАЛОМ (весь час)' : mode === 'all' ? 'ЗАГАЛОМ' : 'ЗА ОБРАНИЙ ПЕРІОД'}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <StatCard label="Замовлень" value={stats.total_orders} color="var(--orange)" />
          <StatCard label="Поповнено" value={`$${stats.total_topups_usd.toFixed(2)}`}
            sub={`⭐${Math.round(stats.total_topups_usd / 0.013)}`} color="#2AABEE" />
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <StatCard label="Виручка" value={`$${stats.total_revenue_usd.toFixed(2)}`}
            sub={`⭐${Math.round(stats.total_revenue_usd / 0.013)}`} color="var(--orange)" />
          <StatCard label="Прибуток" value={`$${stats.total_profit_usd.toFixed(2)}`}
            sub={`витрати $${stats.total_cost_usd.toFixed(2)}`} color={profitColor(stats.total_profit_usd)} />
        </div>

        {/* Funnel — only in all-time/custom */}
        {mode !== 'today' && (<>
          <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--muted)', marginTop: 4, marginBottom: -4 }}>ВОРОНКА</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <StatCard label="Запустили бота" value={stats.total_users} color="#4CAF72" />
            <StatCard label="Купили (унікал.)" value={stats.unique_buyers} color="var(--orange)"
              sub={`${stats.conversion_pct}% конверсія`} />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <StatCard label="Є баланс ⭐" value={stats.users_with_balance} color="var(--gold)" />
            <StatCard label="На балансах" value={`⭐${stats.total_stars_balance}`}
              sub={`$${(stats.total_stars_balance * 0.013).toFixed(2)}`} color="var(--gold)" />
          </div>
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: '12px 14px' }}>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
              Конверсія: {stats.unique_buyers} / {stats.total_users} купили
            </div>
            <div style={{ height: 8, borderRadius: 4, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: 4,
                background: 'linear-gradient(90deg, var(--orange), #ff9500)',
                width: `${Math.min(stats.conversion_pct, 100)}%`, transition: 'width .5s',
              }} />
            </div>
            <div style={{ fontSize: 11, color: 'var(--orange)', marginTop: 4, fontWeight: 700 }}>{stats.conversion_pct}%</div>
          </div>
        </>)}

        {/* Categories */}
        {stats.categories.length > 0 && (<>
          <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--muted)', marginTop: 4, marginBottom: -4 }}>ПО КАТЕГОРІЯХ</div>
          {stats.categories.map(c => (
            <div key={c.category} style={{
              background: 'var(--bg2)', border: '1px solid var(--border)',
              borderRadius: 12, padding: '12px 16px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                {CATEGORY_FLAGS[c.category] || '🌐'} {c.category.toUpperCase()}
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 700, color: 'var(--orange)' }}>{c.count} шт</div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  виручка ${c.revenue_usd.toFixed(2)}
                </div>
                <div style={{ fontSize: 12, fontWeight: 700, color: profitColor(c.profit_usd) }}>
                  прибуток ${c.profit_usd.toFixed(2)}
                </div>
              </div>
            </div>
          ))}
        </>)}

        {/* Danger zone */}
        <div style={{
          marginTop: 8, background: 'rgba(255,60,60,.06)',
          border: '1px solid rgba(255,60,60,.2)', borderRadius: 12, padding: '12px 14px',
        }}>
          <div style={{ fontSize: 12, color: '#ff5555', fontWeight: 700, marginBottom: 8 }}>⚠️ Небезпечна зона</div>
          <button className="btn" disabled={resetting} onClick={handleReset}
            style={{ background: 'rgba(255,60,60,.15)', color: '#ff5555', border: '1px solid rgba(255,60,60,.3)', fontSize: 13 }}>
            {resetting ? '⏳ Скидання...' : '🗑 Скинути всі баланси і статистику'}
          </button>
        </div>

      </>)}
    </div>
  )
}

// ── Users ─────────────────────────────────────────────────────────────────────
function Users() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [data, setData] = useState<{ total: number; pages: number; users: AdminUser[] } | null>(null)
  const [loading, setLoading] = useState(true)
  const [openUser, setOpenUser] = useState<AdminUserDetail | null>(null)
  const [loadingUser, setLoadingUser] = useState(false)

  const load = useCallback((p: number, s: string) => {
    setLoading(true)
    adminApi.users(p, 20, s).then(setData).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load(page, search) }, [page, search, load])

  async function openDetail(id: number) {
    setLoadingUser(true)
    setOpenUser(null)
    try { setOpenUser(await adminApi.userDetail(id)) } finally { setLoadingUser(false) }
  }

  function doSearch() { setPage(1); setSearch(searchInput) }

  if (openUser) return (
    <div>
      <button className="btn btn-secondary" style={{ marginBottom: 12, width: 'auto', padding: '8px 16px' }}
        onClick={() => setOpenUser(null)}>← Назад</button>
      <UserDetail user={openUser} />
    </div>
  )

  return (
    <div>
      {/* Search */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          style={{
            flex: 1, background: 'var(--bg2)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '10px 14px', color: 'var(--text)', fontSize: 14,
          }}
          placeholder="ID / ім'я / @username"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()}
        />
        <button className="btn btn-primary" style={{ width: 'auto', padding: '10px 16px', fontSize: 14 }} onClick={doSearch}>🔍</button>
      </div>

      {data && <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Всього: {data.total}</div>}

      {loading ? (
        [0,1,2,3,4].map(i => <div key={i} className="card" style={{ marginBottom: 6 }}><div className="skeleton" style={{ height: 48 }} /></div>)
      ) : (
        data?.users.map(u => (
          <div key={u.id} className="card" style={{ marginBottom: 6, cursor: 'pointer', padding: '12px 14px' }}
            onClick={() => openDetail(u.id)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                background: 'rgba(255,107,43,.15)', border: '1px solid rgba(255,107,43,.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 800, fontSize: 16,
              }}>{u.name.charAt(0).toUpperCase()}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {u.name}
                  {u.is_admin && <span style={{ background: 'rgba(255,184,48,.2)', color: 'var(--gold)', fontSize: 10, padding: '1px 6px', borderRadius: 6 }}>ADMIN</span>}
                  {u.is_banned && <span style={{ background: 'rgba(255,60,60,.2)', color: '#ff5555', fontSize: 10, padding: '1px 6px', borderRadius: 6 }}>BAN</span>}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>
                  {u.username ? `@${u.username} · ` : ''}{fmt(u.created_at)}
                </div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontWeight: 700, color: 'var(--orange)', fontSize: 14 }}>⭐{u.balance_stars}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>{u.orders_count} замовл.</div>
              </div>
            </div>
          </div>
        ))
      )}

      {loadingUser && <div style={{ textAlign: 'center', padding: 20, color: 'var(--muted)' }}>⏳</div>}
      {data && <Pagination page={page} pages={data.pages} onPage={setPage} />}
    </div>
  )
}

function UserDetail({ user }: { user: AdminUserDetail }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Hero */}
      <div style={{
        background: 'var(--bg2)', border: '1px solid var(--border)',
        borderRadius: 16, padding: '16px',
      }}>
        <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 4 }}>{user.name}</div>
        {user.username && <div style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 8 }}>@{user.username}</div>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ background: 'rgba(255,107,43,.12)', border: '1px solid rgba(255,107,43,.25)', borderRadius: 8, padding: '4px 10px', fontSize: 13, fontWeight: 700 }}>
            ⭐{user.balance_stars}
          </span>
          <span style={{ background: 'rgba(42,171,238,.1)', border: '1px solid rgba(42,171,238,.2)', borderRadius: 8, padding: '4px 10px', fontSize: 13 }}>
            ID: {user.id}
          </span>
          {user.is_banned && <span style={{ background: 'rgba(255,60,60,.15)', color: '#ff5555', borderRadius: 8, padding: '4px 10px', fontSize: 13 }}>🚫 BANNED</span>}
        </div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>Реєстрація: {fmt(user.created_at)}</div>
        {user.referred_by_id && <div style={{ fontSize: 12, color: 'var(--muted)' }}>Запросив: #{user.referred_by_id}</div>}
      </div>

      {/* Orders */}
      <div style={{ fontWeight: 700, fontSize: 14, marginTop: 4 }}>Замовлення ({user.orders.length})</div>
      {user.orders.length === 0
        ? <div className="card" style={{ textAlign: 'center', color: 'var(--muted)' }}>Немає</div>
        : user.orders.map(o => (
          <div key={o.id} className="card" style={{ padding: '12px 14px', marginBottom: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>
                  #{String(o.id).padStart(5,'0')} · {CATEGORY_FLAGS[o.category||''] || '🌐'} {(o.category||'?').toUpperCase()}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{fmt(o.created_at)}</div>
                {o.delivered_data && <div style={{ fontSize: 12, color: '#4CAF72', marginTop: 2 }}>📱 {o.delivered_data}</div>}
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 700, color: 'var(--orange)' }}>⭐{Math.round(o.price_usd / 0.013)}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>${o.price_usd.toFixed(2)}</div>
              </div>
            </div>
          </div>
        ))
      }

      {/* Topups */}
      <div style={{ fontWeight: 700, fontSize: 14, marginTop: 4 }}>Поповнення ({user.topups.length})</div>
      {user.topups.length === 0
        ? <div className="card" style={{ textAlign: 'center', color: 'var(--muted)' }}>Немає</div>
        : user.topups.map(t => (
          <div key={t.id} className="card" style={{ padding: '12px 14px', marginBottom: 6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: 13, color: 'var(--muted)' }}>{fmt(t.created_at)}</div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 700, color: '#2AABEE' }}>⭐{Math.round(t.amount_usd / 0.013)}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>${t.amount_usd.toFixed(2)}</div>
              </div>
            </div>
          </div>
        ))
      }
    </div>
  )
}

// ── Orders ────────────────────────────────────────────────────────────────────
function Orders() {
  const [page, setPage] = useState(1)
  const [data, setData] = useState<{ total: number; pages: number; orders: AdminOrderRow[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    adminApi.orders(page).then(setData).finally(() => setLoading(false))
  }, [page])

  return (
    <div>
      {data && <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Всього замовлень: {data.total}</div>}

      {loading ? (
        [0,1,2,3].map(i => <div key={i} className="card" style={{ marginBottom: 6 }}><div className="skeleton" style={{ height: 52 }} /></div>)
      ) : (
        data?.orders.map(o => (
          <div key={o.id} className="card" style={{ marginBottom: 6, padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ fontSize: 20 }}>{CATEGORY_FLAGS[o.category||''] || '🌐'}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 13 }}>
                  #{String(o.id).padStart(5,'0')} · {(o.category||'?').toUpperCase()}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>
                  {o.username ? `@${o.username}` : o.user_name} · {fmt(o.created_at)}
                </div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontWeight: 700, color: 'var(--orange)', fontSize: 13 }}>⭐{Math.round(o.price_usd / 0.013)}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>${o.price_usd.toFixed(2)}</div>
              </div>
            </div>
          </div>
        ))
      )}

      {data && <Pagination page={page} pages={data.pages} onPage={setPage} />}
    </div>
  )
}

// ── Topups ────────────────────────────────────────────────────────────────────
function Topups() {
  const [page, setPage] = useState(1)
  const [data, setData] = useState<{ total: number; pages: number; topups: AdminTopupRow[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    adminApi.topups(page).then(setData).finally(() => setLoading(false))
  }, [page])

  return (
    <div>
      {data && <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Всього поповнень: {data.total}</div>}

      {loading ? (
        [0,1,2,3].map(i => <div key={i} className="card" style={{ marginBottom: 6 }}><div className="skeleton" style={{ height: 48 }} /></div>)
      ) : (
        data?.topups.map(t => (
          <div key={t.id} className="card" style={{ marginBottom: 6, padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>
                  {t.username ? `@${t.username}` : t.user_name}
                  <span style={{ color: 'var(--muted)', fontSize: 11, marginLeft: 6 }}>#{t.user_id}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 1 }}>{fmt(t.created_at)}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: 700, color: '#2AABEE', fontSize: 14 }}>⭐{t.amount_stars}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>${t.amount_usd.toFixed(2)}</div>
              </div>
            </div>
          </div>
        ))
      )}

      {data && <Pagination page={page} pages={data.pages} onPage={setPage} />}
    </div>
  )
}

// ── Broadcast ─────────────────────────────────────────────────────────────────
function Broadcast() {
  const [text, setText] = useState('')
  const [parseMode, setParseMode] = useState<'HTML' | 'Markdown'>('HTML')
  const [status, setStatus] = useState<BroadcastStatus | null>(null)
  const [sending, setSending] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    adminApi.broadcastStatus().then(setStatus).catch(() => {})
  }, [])

  function startPoll() {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      const s = await adminApi.broadcastStatus().catch(() => null)
      if (s) {
        setStatus(s)
        if (!s.running && pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
          setSending(false)
        }
      }
    }, 1000)
  }

  async function send() {
    if (!text.trim()) return
    setSending(true)
    try {
      await adminApi.broadcast(text, parseMode)
      setStatus({ running: true, sent: 0, failed: 0, total: 0, text })
      startPoll()
    } catch (e: any) {
      alert(e.message)
      setSending(false)
    }
  }

  const progress = status && status.total > 0
    ? Math.round((status.sent + status.failed) / status.total * 100)
    : 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Status */}
      {status?.running && (
        <div style={{
          background: 'rgba(42,171,238,.1)', border: '1px solid rgba(42,171,238,.3)',
          borderRadius: 12, padding: '12px 14px',
        }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#2AABEE', marginBottom: 8 }}>
            📤 Розсилка виконується...
          </div>
          <div style={{ height: 6, background: 'rgba(255,255,255,.1)', borderRadius: 3, marginBottom: 6, overflow: 'hidden' }}>
            <div style={{ height: '100%', background: '#2AABEE', borderRadius: 3, width: `${progress}%`, transition: 'width .3s' }} />
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>
            ✅ {status.sent} надіслано · ❌ {status.failed} помилок · з {status.total}
          </div>
        </div>
      )}
      {status && !status.running && status.total > 0 && (
        <div style={{
          background: 'rgba(76,175,114,.1)', border: '1px solid rgba(76,175,114,.3)',
          borderRadius: 12, padding: '12px 14px',
        }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#4CAF72', marginBottom: 4 }}>✅ Розсилку завершено</div>
          <div style={{ fontSize: 13, color: 'var(--muted)' }}>
            Надіслано: {status.sent} · Помилки (заблоковані): {status.failed} · Всього: {status.total}
          </div>
        </div>
      )}

      {/* Composer */}
      <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 14, padding: 14 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Формат</div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {(['HTML', 'Markdown'] as const).map(m => (
            <button key={m} onClick={() => setParseMode(m)}
              style={{
                padding: '6px 14px', fontSize: 13, borderRadius: 8, cursor: 'pointer',
                background: parseMode === m ? 'rgba(255,107,43,.2)' : 'transparent',
                color: parseMode === m ? 'var(--orange)' : 'var(--muted)',
                border: parseMode === m ? '1px solid rgba(255,107,43,.4)' : '1px solid var(--border)',
              }}>
              {m}
            </button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>Текст повідомлення</div>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          rows={6}
          placeholder={parseMode === 'HTML'
            ? '<b>Жирний</b>, <i>курсив</i>, <code>код</code>'
            : '*Жирний*, _курсив_, `код`'}
          style={{
            width: '100%', background: 'rgba(255,255,255,.05)',
            border: '1px solid var(--border)', borderRadius: 10,
            padding: '10px 12px', color: 'var(--text)', fontSize: 14,
            resize: 'vertical', fontFamily: 'inherit', boxSizing: 'border-box',
          }}
        />
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6, marginBottom: 12 }}>
          Буде надіслано <b style={{ color: 'var(--text)' }}>всім незаблокованим</b> користувачам
        </div>

        <button
          className="btn btn-primary"
          disabled={sending || !text.trim() || (status?.running ?? false)}
          onClick={send}
        >
          {sending || status?.running ? '📤 Надсилається...' : '📢 Розіслати всім'}
        </button>
      </div>
    </div>
  )
}

// ── Main Admin page ───────────────────────────────────────────────────────────
const TABS: { id: AdminTab; label: string }[] = [
  { id: 'overview',  label: '📊 Огляд' },
  { id: 'users',     label: '👥 Юзери' },
  { id: 'orders',    label: '📦 Замовл.' },
  { id: 'topups',    label: '💰 Поповн.' },
  { id: 'broadcast', label: '📢 Розсилка' },
]

export default function Admin() {
  const [tab, setTab] = useState<AdminTab>('overview')

  return (
    <div className="page">
      <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 12 }}>⚙️ Адмін-панель</div>

      {/* Tab bar — two rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14 }}>
        <div style={{
          display: 'flex', gap: 4,
          background: 'var(--bg2)', borderRadius: 12, padding: 4,
          border: '1px solid var(--border)',
        }}>
          {TABS.slice(0, 3).map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              flex: 1, padding: '8px 4px', fontSize: 11, fontWeight: tab === t.id ? 700 : 500,
              background: tab === t.id ? 'rgba(255,107,43,.2)' : 'transparent',
              color: tab === t.id ? 'var(--orange)' : 'var(--muted)',
              border: tab === t.id ? '1px solid rgba(255,107,43,.35)' : '1px solid transparent',
              borderRadius: 8, cursor: 'pointer', transition: 'all .15s',
            }}>{t.label}</button>
          ))}
        </div>
        <div style={{
          display: 'flex', gap: 4,
          background: 'var(--bg2)', borderRadius: 12, padding: 4,
          border: '1px solid var(--border)',
        }}>
          {TABS.slice(3).map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              flex: 1, padding: '8px 4px', fontSize: 11, fontWeight: tab === t.id ? 700 : 500,
              background: tab === t.id ? 'rgba(255,107,43,.2)' : 'transparent',
              color: tab === t.id ? 'var(--orange)' : 'var(--muted)',
              border: tab === t.id ? '1px solid rgba(255,107,43,.35)' : '1px solid transparent',
              borderRadius: 8, cursor: 'pointer', transition: 'all .15s',
            }}>{t.label}</button>
          ))}
        </div>
      </div>

      {tab === 'overview'  && <Overview />}
      {tab === 'users'     && <Users />}
      {tab === 'orders'    && <Orders />}
      {tab === 'topups'    && <Topups />}
      {tab === 'broadcast' && <Broadcast />}
    </div>
  )
}
