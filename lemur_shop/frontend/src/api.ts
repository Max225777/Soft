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
  starsRate:    () => req<{ stars_per_usd: number }>('/stars/rate'),
  starsInvoice: (amount_usd: number) => req<{ invoice_url: string; stars: number; amount_usd: number }>('/stars/invoice', { method: 'POST', body: JSON.stringify({ amount_usd }) }),
}

export interface Me {
  id: number; name: string; username: string | null
  lang: 'ua' | 'ru' | 'en'
  balance_usd: number; balance_uah: number; balance_rub: number
  rate_uah: number; rate_rub: number
  orders_count: number; total_spent_usd: number; is_admin: boolean
}
export interface Category { category: string; flag: string; title: string; price_usd: number }
export interface BuyResult { order_id: number; phone: string; created_at: string }
export interface Order {
  id: number; price_usd: number; status: string
  created_at: string; delivered_data: string | null
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string
        expand(): void
        close(): void
        openInvoice(url: string, callback: (status: string) => void): void
      }
    }
  }
}
