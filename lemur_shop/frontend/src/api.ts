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

export interface ReferralUser {
  name: string
  username: string | null
  is_buyer: boolean
}
export interface Referral {
  referral_code: string
  ref_count: number
  buyers_count: number
  earned_stars: number
  referrals: ReferralUser[]
}

export interface NftItem {
  id: number; username: string; description: string | null
  price_stars: number; duration_days: number
  is_available: boolean; currently_rented: boolean
  expires_at: string | null
}
export interface AdminNftItem extends NftItem {
  added_by: number; created_at: string
}
export interface AdminNftRental {
  id: number; nft_id: number; username: string
  user_id: number; user_name: string; user_username: string | null
  started_at: string; expires_at: string; status: string; days_left: number
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
  referral:     () => req<Referral>('/referral'),
  leaderboard:        (period: 'all' | 'today') => req<LeaderRow[]>(`/leaderboard?period=${period}`),
  leaderboardRefs:    (period: 'all' | 'today') => req<RefLeaderRow[]>(`/leaderboard/referrals?period=${period}`),
  promoRedeem:  (code: string) => req<{ ok: boolean; stars: number }>('/promo/redeem', { method: 'POST', body: JSON.stringify({ code }) }),
  nftList:      (search?: string) => req<NftItem[]>(`/nft/list${search ? '?search=' + encodeURIComponent(search) : ''}`),
  nftBuy:       (nft_id: number) => req<{ order_id: number; stars_spent: number; expires_at: string }>('/nft/buy', { method: 'POST', body: JSON.stringify({ nft_id }) }),
}

export interface FortuneCat {
  seg: number; cat: string; label: string; emoji: string; color: string; threshold: number
}
export interface FortunePrizesInfo {
  cats: FortuneCat[]; pool_balance: number; spin_cost: number
}
export interface FortunePoolInfo {
  balance_stars: number; total_spins: number; total_admin_profit_stars: number
  total_prizes_count: number; total_prizes_stars: number
  acc_claims?: number; acc_cost_usd?: number; acc_value_stars?: number; stars_claims?: number
}
export interface FortuneSpinResult {
  spin_id: number; won: boolean
  prize_cat: string | null; prize_seg: number
  prize_label: string; prize_emoji: string; prize_color: string
  phone: string | null; order_id: number | null
  pool_balance: number; pool_threshold: number; new_balance: number
  stars_option: number | null
  was_downgraded: boolean; rolled_label: string | null
}
export interface FortuneClaimResult {
  ok: boolean; choice: string
  phone: string | null; order_id: number | null; stars_awarded: number | null
}
export interface FortuneRecentWin { user_display: string; prize_label: string; created_at: string | null }

export const fortuneApi = {
  prizes: () => req<FortunePrizesInfo>('/fortune/prizes'),
  pool:   () => req<FortunePoolInfo>('/fortune/pool'),
  spin:   () => req<FortuneSpinResult>('/fortune/spin', { method: 'POST' }),
  recent: () => req<FortuneRecentWin[]>('/fortune/recent'),
  claim:  (spin_id: number, choice: 'account' | 'stars') =>
    req<FortuneClaimResult>('/fortune/claim', { method: 'POST', body: JSON.stringify({ spin_id, choice }) }),
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

export interface BioPromoStatus {
  joined: boolean; is_active: boolean; reward_tier: number; total_rewarded: number
  hours_until_next: number | null; last_rewarded_at: string | null
  rewarded?: boolean; stars_rewarded?: number
}

export const bioPromoApi = {
  status: () => req<BioPromoStatus>('/bio-promo/status'),
  check:  () => req<BioPromoStatus>('/bio-promo/check', { method: 'POST' }),
}

export interface BioPromoParticipant {
  user_id: number; name: string; username: string | null
  is_active: boolean; reward_tier: number; total_rewarded: number
  joined_at: string; last_check_at: string | null; last_rewarded_at: string | null
}
export interface BioPromoParticipantsPage {
  items: BioPromoParticipant[]; total: number; page: number; pages: number
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
  earningsChart:   (dateFrom?: string, dateTo?: string) => {
    const p = new URLSearchParams()
    if (dateFrom) p.set('date_from', dateFrom)
    if (dateTo)   p.set('date_to', dateTo)
    const qs = p.toString()
    return req<EarningsChart>(`/admin/earnings-chart${qs ? '?' + qs : ''}`)
  },
  users:           (page: number, limit = 20, search = '') => req<AdminUsersPage>(`/admin/users?page=${page}&limit=${limit}&search=${encodeURIComponent(search)}`),
  userDetail:      (id: number) => req<AdminUserDetail>(`/admin/user/${id}`),
  orders:          (page: number, limit = 30) => req<AdminOrdersPage>(`/admin/orders?page=${page}&limit=${limit}`),
  topups:          (page: number, limit = 30) => req<AdminTopupsPage>(`/admin/topups?page=${page}&limit=${limit}`),
  broadcast:       (text: string, parse_mode = 'HTML') => req<{ ok: boolean; total: number }>('/admin/broadcast', { method: 'POST', body: JSON.stringify({ text, parse_mode }) }),
  broadcastStatus: () => req<BroadcastStatus>('/admin/broadcast/status'),
  resetStats:      () => req<{ ok: boolean }>('/admin/reset-stats', { method: 'POST' }),
  bioPromoList:    (page: number, limit = 30) => req<BioPromoParticipantsPage>(`/admin/bio-promo?page=${page}&limit=${limit}`),
  referralStats:   () => req<AdminReferralStats>('/admin/referrals'),
  referralInvited: (referrerId: number) => req<AdminReferralInvitedUser[]>(`/admin/referrals/${referrerId}/invited`),
  promoList:       () => req<AdminPromoCode[]>('/admin/promo/list'),
  promoCreate:     (code: string, reward_stars: number, max_activations: number) =>
                     req<{ ok: boolean }>('/admin/promo/create', { method: 'POST', body: JSON.stringify({ code, reward_stars, max_activations }) }),
  promoToggle:     (id: number) => req<{ ok: boolean; is_active: boolean }>(`/admin/promo/${id}/toggle`, { method: 'POST' }),
  promoActivations:(id: number) => req<AdminPromoActivation[]>(`/admin/promo/${id}/activations`),
  fortune:         () => req<FortunePoolInfo>('/admin/fortune'),
  nftList:         () => req<AdminNftItem[]>('/admin/nft/list'),
  nftAdd:          (username: string, description: string, price_stars: number, duration_days: number) => req<{ ok: boolean; id: number }>('/admin/nft/add', { method: 'POST', body: JSON.stringify({ username, description, price_stars, duration_days }) }),
  nftEdit:         (id: number, data: Partial<{ username: string; description: string; price_stars: number; duration_days: number; is_available: boolean }>) => req<{ ok: boolean }>(`/admin/nft/${id}/edit`, { method: 'POST', body: JSON.stringify(data) }),
  nftDelete:       (id: number) => req<{ ok: boolean }>(`/admin/nft/${id}`, { method: 'DELETE' }),
  nftRentals:      () => req<AdminNftRental[]>('/admin/nft/rentals'),
}

export interface Me {
  id: number; name: string; username: string | null
  lang: 'ua' | 'ru' | 'en'
  balance_stars: number
  balance_usd: number; balance_uah: number; balance_rub: number
  rate_uah: number; rate_rub: number
  orders_count: number; is_admin: boolean; preview_mode: boolean
  bot_username: string
}
export interface SmmService {
  key: string; service_id: number | string; title: string; flag: string; description: string
  price_per_100_stars: number; min: number; max: number; step: number; unit_size: number
}
export interface Category { category: string; flag: string; title: string; title_ru: string; title_ua: string; phone_prefix: string; price_usd: number; price_stars: number; discount_stars?: number }
export interface BuyResult { order_id: number; phone: string; created_at: string }
export interface Order {
  id: number; price_usd: number; status: string
  category: string | null; smm_quantity: number
  created_at: string; delivered_data: string | null
}
export interface LeaderRow {
  rank: number; name: string; username: string | null
  orders_count: number; total_stars: number; is_me: boolean
}
export interface RefLeaderRow {
  rank: number; name: string; username: string | null
  invited_count: number; earned_stars: number; is_me: boolean
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
  bio_promo_total: number; bio_promo_active: number; bio_promo_tier2: number; bio_promo_stars: number
  categories: StatsCatRow[]
  accounts: StatsGroup
  smm: StatsGroup
}
export interface EarningsDay {
  date: string
  stars_usd: number; stars_count: number
  crypto_usd: number; crypto_count: number
  admin_usd: number; admin_count: number
  total_usd: number
  revenue_usd: number; cost_usd: number; profit_usd: number
}
export interface EarningsChart {
  date_from: string; date_to: string
  days: EarningsDay[]
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
  amount_usd: number; amount_stars: number; method: string; charge_id: string | null
  admin_id: number; created_at: string
}
export interface TopupMethodStat { count: number; stars: number; usd: number }
export interface AdminTopupsPage {
  total: number; page: number; pages: number; topups: AdminTopupRow[]
  stats: {
    by_method: Record<string, TopupMethodStat>
    total_stars: number; total_usd: number
    promo: { count: number; stars: number }
  }
}

export interface AdminReferrerRow {
  id: number; name: string; username: string | null
  invited: number; buyers: number; earned_stars: number
}
export interface AdminReferralStats {
  invited_today: number; invited_total: number
  referrers: AdminReferrerRow[]
  payouts: { total_count: number; total_stars: number; today_count: number; today_stars: number }
}
export interface AdminReferralInvitedUser {
  id: number; name: string; username: string | null
  joined_at: string; is_buyer: boolean
}
export interface AdminPromoCode {
  id: number; code: string; reward_stars: number
  max_activations: number; activations: number
  is_active: boolean; created_at: string
}
export interface AdminPromoActivation {
  user_id: number; name: string; username: string | null; activated_at: string
}

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
