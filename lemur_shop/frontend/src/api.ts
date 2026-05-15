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
  me:         () => req<Me>('/me'),
  setLang:    (lang: string) => req<{ ok: boolean }>('/set-lang', { method: 'POST', body: JSON.stringify({ lang }) }),
  categories: () => req<Category[]>('/categories'),
  buy:        (category: string) => req<BuyResult>('/buy', { method: 'POST', body: JSON.stringify({ category }) }),
  orders:     () => req<Order[]>('/orders'),
}

export interface Me {
  id: number; name: string; username: string | null
  lang: 'ua' | 'ru' | 'en'
  balance_usd: number; balance_uah: number; balance_rub: number
  rate_uah: number; rate_rub: number
  orders_count: number; is_admin: boolean
}
export interface Category { category: string; flag: string; title: string; price_usd: number }
export interface BuyResult { order_id: number; phone: string; code: string; created_at: string }
export interface Order {
  id: number; price_usd: number; status: string
  created_at: string; delivered_data: string | null
}

declare global {
  interface Window { Telegram?: { WebApp: { initData: string; expand(): void; close(): void } } }
}
