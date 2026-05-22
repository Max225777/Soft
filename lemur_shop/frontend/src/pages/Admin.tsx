import { useState, useEffect, useCallback } from 'react'
import { adminApi, type AdminStats, type AdminUser, type AdminUserDetail, type AdminOrderRow, type AdminTopupRow } from '../api'

type AdminTab = 'overview' | 'users' | 'orders' | 'topups'

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
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi.stats().then(setStats).finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)' }}>⏳ Завантаження...</div>
  if (!stats) return <div style={{ padding: 20, color: 'var(--red)' }}>Помилка завантаження</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Today */}
      <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--muted)', marginBottom: -4 }}>СЬОГОДНІ</div>
      <div style={{ display: 'flex', gap: 8 }}>
        <StatCard label="Нових юзерів" value={stats.new_users_today} color="#4CAF72" />
        <StatCard label="Замовлень" value={stats.orders_today} color="var(--orange)" />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <StatCard label="Дохід" value={`$${stats.revenue_today.toFixed(2)}`} color="var(--orange)"
          sub={`⭐${Math.round(stats.revenue_today / 0.013)}`} />
        <StatCard label="Поповнень" value={`$${stats.topups_today.toFixed(2)}`} color="#2AABEE"
          sub={`⭐${Math.round(stats.topups_today / 0.013)}`} />
      </div>

      {/* All time */}
      <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--muted)', marginTop: 4, marginBottom: -4 }}>ВСЕ ВДЕНЬ</div>
      <div style={{ display: 'flex', gap: 8 }}>
        <StatCard label="Всього юзерів" value={stats.total_users} color="#4CAF72" />
        <StatCard label="Замовлень" value={stats.total_orders} color="var(--orange)" />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <StatCard label="Загальний дохід" value={`$${stats.total_revenue_usd.toFixed(2)}`}
          sub={`⭐${Math.round(stats.total_revenue_usd / 0.013)}`} color="var(--orange)" />
        <StatCard label="Поповнено" value={`$${stats.total_topups_usd.toFixed(2)}`}
          sub={`⭐${Math.round(stats.total_topups_usd / 0.013)}`} color="#2AABEE" />
      </div>
      <StatCard label="⭐ На балансах юзерів" value={`⭐${stats.total_stars_balance}`}
        sub={`$${(stats.total_stars_balance * 0.013).toFixed(2)}`} color="var(--gold)" />

      {/* Categories */}
      {stats.categories.length > 0 && (
        <>
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
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>${c.revenue_usd.toFixed(2)}</div>
              </div>
            </div>
          ))}
        </>
      )}
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

// ── Main Admin page ───────────────────────────────────────────────────────────
const TABS: { id: AdminTab; label: string }[] = [
  { id: 'overview', label: '📊 Огляд' },
  { id: 'users',    label: '👥 Юзери' },
  { id: 'orders',   label: '📦 Замовл.' },
  { id: 'topups',   label: '💰 Поповн.' },
]

export default function Admin() {
  const [tab, setTab] = useState<AdminTab>('overview')

  return (
    <div className="page">
      <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 12 }}>⚙️ Адмін-панель</div>

      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: 6, marginBottom: 14,
        background: 'var(--bg2)', borderRadius: 14, padding: 4,
        border: '1px solid var(--border)',
      }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              flex: 1, padding: '8px 4px', fontSize: 12, fontWeight: tab === t.id ? 700 : 500,
              background: tab === t.id ? 'rgba(255,107,43,.2)' : 'transparent',
              color: tab === t.id ? 'var(--orange)' : 'var(--muted)',
              border: tab === t.id ? '1px solid rgba(255,107,43,.35)' : '1px solid transparent',
              borderRadius: 10, cursor: 'pointer', transition: 'all .15s',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <Overview />}
      {tab === 'users'    && <Users />}
      {tab === 'orders'   && <Orders />}
      {tab === 'topups'   && <Topups />}
    </div>
  )
}
