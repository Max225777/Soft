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
  me:       () => req<Me>('/me'),
  shop:     (cat: string) => req<Item[]>(`/shop/${cat}`),
  buy:      (item_id: number, price: number, category: string) =>
              req<BuyResult>('/buy', { method: 'POST', body: JSON.stringify({ item_id, price, category }) }),
  orders:   () => req<Order[]>('/orders'),
  referral: () => req<Referral>('/referral'),
}

export interface Me {
  id: number; name: string; username: string | null
  lang: 'ua' | 'ru'; balance_usd: number; balance_uah: number; balance_rub: number
  orders_count: number; is_admin: boolean
}
export interface Item  { item_id: number; title: string; price: number; reg_date: string }
export interface BuyResult { order_id: number; phone: string; code: string }
export interface Order { id: number; price_usd: number; status: string; created_at: string }
export interface Referral {
  referral_code: string; ref_count: number; earned_usd: number; bonus_pct: number
}

declare global {
  interface Window { Telegram?: { WebApp: { initData: string; expand(): void; close(): void } } }
}
