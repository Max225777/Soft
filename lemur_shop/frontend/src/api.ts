const BASE = '/api'
const initData = () => window.Telegram?.WebApp?.initData ?? ''

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + path, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      'x-init-data': initData(),
      ...opts.headers,
    },
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new Error(err.detail ?? 'Request failed')
  }
  return r.json()
}

export const api = {
  me:           () => req<Me>('/me'),
  setLang:      (lang: string) => req<{ ok: boolean }>('/set-lang', { method: 'POST', body: JSON.stringify({ lang }) }),
  categories:   () => req<Category[]>('/categories'),
  buy:          (category: string) => req<BuyResult>('/buy', { method: 'POST', body: JSON.stringify({ category }) }),
  orders:       () => req<Order[]>('/orders'),
  getCode:      (orderId: number) => req<{ code: string }>(`/get-code/${orderId}`, { method: 'POST' }),
  checkSub:     () => req<{ subscribed: boolean }>('/check-sub'),
  cryptoCreate:   (amount_usd: number) => req<{ url: string; invoice_id: number }>('/crypto/create', { method: 'POST', body: JSON.stringify({ amount_usd }) }),
  starsRate:    () => req<{ stars_per_usd: number }>('/stars/rate'),
  starsInvoice: (stars: number) => req<{ invoice_url: string; stars: number; amount_usd: number }>('/stars/invoice', { method: 'POST', body: JSON.stringify({ stars }) }),
  starsBuy:     (stars: number, amount_usd: number) => req<{ ok: boolean }>('/stars/buy', { method: 'POST', body: JSON.stringify({ stars, amount_usd }) }),
}

export const smmApi = {
  services:  () => req<SmmService[]>('/smm/services'),
  reactions: () => req<{ emoji: string; service_id: number }[]>('/smm/reactions'),
  order:     (service_key: string, link: string, quantity: number, reaction?: string) =>
               req<{ order_id: number; stars_spent: number }>('/smm/order', { method: 'POST', body: JSON.stringify({ service_key, link, quantity, reaction }) }),
  status:    (order_id: number) => req<{ status: string; remains: string; start_count: string }>(`/smm/status/${order_id}`),
}

export const gameApi = {
  status: () => req<{ can_play_free: boolean; min_bet: number; balance_stars: number }>('/game/status'),
  start:  (bet: number) => req<{ token: string; is_free: boolean; bet: number }>('/game/start', { method: 'POST', body: JSON.stringify({ bet }) }),
  finish: (token: string, score: number) => req<{ score: number; bet: number; multiplier: number; stars_won: number; net: number; new_balance: number }>('/game/finish', { method: 'POST', body: JSON.stringify({ token, score }) }),
}

export interface WheelParticipantInfo {
  name: string; is_you: boolean; is_bot: boolean
}
export interface WheelRoomInfo {
  id: number; stake: number; max_players: number; status: string
  participants: WheelParticipantInfo[]
  winner_name: string | null; winner_is_you: boolean; payout: number
  new_balance: number
}
export interface WheelLobbyEntry { stake: number; max_players: number; waiting: number }

export const wheelApi = {
  lobby:  () => req<WheelLobbyEntry[]>('/wheel/lobby'),
  join:   (stake: number, max_players: number) =>
            req<{ room_id: number }>('/wheel/join', { method: 'POST', body: JSON.stringify({ stake, max_players }) }),
  room:   (id: number) => req<WheelRoomInfo>(`/wheel/room/${id}`),
}

export const adminApi = {
  stats:           (dateFrom?: string, dateTo?: string) => {
    const p = new URLSearchParams()
    if (dateFrom) p.set('date_from', dateFrom)
    if (dateTo)   p.set('date_to', dateTo)
    const qs = p.toString()
    return req<AdminStats>(`/admin/stats${qs ? '?' + qs : ''}`)
  },
  users:           (page: number, limit = 20, search = '') => req<AdminUsersPage>(`/admin/users?page=${page}&limit=${limit}&search=${encodeURIComponent(search)}`),
  userDetail:      (id: number) => req<AdminUserDetail>(`/admin/user/${id}`),
  orders:          (page: number, limit = 30) => req<AdminOrdersPage>(`/admin/orders?page=${page}&limit=${limit}`),
  topups:          (page: number, limit = 30) => req<AdminTopupsPage>(`/admin/topups?page=${page}&limit=${limit}`),
  broadcast:       (text: string, parse_mode = 'HTML') => req<{ ok: boolean; total: number }>('/admin/broadcast', { method: 'POST', body: JSON.stringify({ text, parse_mode }) }),
  broadcastStatus: () => req<BroadcastStatus>('/admin/broadcast/status'),
  resetStats:      () => req<{ ok: boolean }>('/admin/reset-stats', { method: 'POST' }),
}

export interface Me {
  id: number; name: string; username: string | null
  lang: 'ua' | 'ru' | 'en'
  balance_stars: number
  balance_usd: number; balance_uah: number; balance_rub: number
  rate_uah: number; rate_rub: number
  orders_count: number; is_admin: boolean; preview_mode: boolean
}
export interface SmmService {
  key: string; service_id: number | string; title: string; flag: string; description: string
  price_per_100_stars: number; min: number; max: number; step: number; unit_size: number
}
export interface Category { category: string; flag: string; title: string; price_usd: number; price_stars: number; discount_stars?: number }
export interface BuyResult { order_id: number; phone: string; created_at: string }
export interface Order {
  id: number; price_usd: number; status: string
  created_at: string; delivered_data: string | null
}

export interface StatsCatRow {
  category: string; group: 'account' | 'smm'; count: number; smm_quantity: number
  revenue_usd: number; cost_usd: number; profit_usd: number
}
export interface StatsGroup {
  count: number; smm_quantity: number
  revenue_usd: number; cost_usd: number; profit_usd: number; rows: StatsCatRow[]
}
export interface AdminStats {
  total_users: number; unique_buyers: number; users_with_balance: number; conversion_pct: number
  total_orders: number; avg_order_usd: number
  total_revenue_usd: number; total_cost_usd: number; total_profit_usd: number
  total_topups_usd: number; total_stars_balance: number
  new_users_today: number; orders_today: number
  revenue_today: number; cost_today: number; profit_today: number; topups_today: number
  categories: StatsCatRow[]
  accounts: StatsGroup
  smm: StatsGroup
}
export interface BroadcastStatus {
  running: boolean; sent: number; failed: number; total: number; text: string
}
export interface AdminUser {
  id: number; name: string; username: string | null
  balance_stars: number; orders_count: number; topups_usd: number
  is_admin: boolean; is_banned: boolean; created_at: string
}
export interface AdminUsersPage { total: number; page: number; pages: number; users: AdminUser[] }
export interface AdminOrderDetail {
  id: number; category: string | null; price_usd: number; status: string
  delivered_data: string | null; created_at: string
}
export interface AdminTopupDetail { id: number; amount_usd: number; created_at: string }
export interface AdminUserDetail {
  id: number; name: string; username: string | null
  balance_stars: number; balance_usd: number
  is_banned: boolean; created_at: string; referred_by_id: number | null
  orders: AdminOrderDetail[]; topups: AdminTopupDetail[]
}
export interface AdminOrderRow {
  id: number; user_id: number; username: string | null; user_name: string
  category: string | null; price_usd: number; status: string; created_at: string
}
export interface AdminOrdersPage { total: number; page: number; pages: number; orders: AdminOrderRow[] }
export interface AdminTopupRow {
  id: number; user_id: number; username: string | null; user_name: string
  amount_usd: number; amount_stars: number; created_at: string
}
export interface AdminTopupsPage { total: number; page: number; pages: number; topups: AdminTopupRow[] }

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string
        expand(): void
        close(): void
        openLink(url: string): void
        openInvoice(url: string, callback: (status: string) => void): void
      }
    }
  }
}
