import { useState, useEffect } from 'react'
import { smmApi, type Me, type SmmService } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { me: Me | null; lang: Lang; onRefresh: () => void }

const SERVICE_KEY = 'tg_subscribers'

export default function Boost({ me, lang, onRefresh }: Props) {
  const T = getT(lang)
  const [services, setServices] = useState<SmmService[]>([])
  const [link, setLink] = useState('')
  const [quantity, setQuantity] = useState(100)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<{ order_id: number; stars_spent: number } | null>(null)

  useEffect(() => {
    smmApi.services().then(setServices).catch(() => {})
  }, [])

  const svc = services[0]
  const priceStars = svc ? Math.round(quantity / 100 * svc.price_per_100_stars) : 0
  const balance = me?.balance_stars ?? 0
  const canBuy = link.trim().length > 0 && balance >= priceStars && !loading

  async function submit() {
    if (!svc || !canBuy) return
    setLoading(true); setError(null)
    try {
      const res = await smmApi.order(SERVICE_KEY, link.trim(), quantity)
      setSuccess(res)
      onRefresh()
      setLink('')
      setQuantity(100)
    } catch (e: any) {
      if (e.message === 'insufficient_balance') {
        setError(lang === 'ru' ? 'Недостаточно звёзд' : lang === 'ua' ? 'Недостатньо зірок' : 'Insufficient stars')
      } else {
        setError(e.message ?? 'Ошибка')
      }
    } finally {
      setLoading(false)
    }
  }

  const label = {
    ru: { title: 'Накрутка', desc: 'Продвижение Telegram каналов', link_ph: 'Ссылка на канал/группу', qty: 'Количество', order: 'Заказать', cost: 'Стоимость', guarantee: 'Гарантия 365 дней', done: 'Заказ принят!' },
    ua: { title: 'Накрутка', desc: 'Просування Telegram каналів', link_ph: 'Посилання на канал/групу', qty: 'Кількість', order: 'Замовити', cost: 'Вартість', guarantee: 'Гарантія 365 днів', done: 'Замовлення прийнято!' },
    en: { title: 'Boost', desc: 'Telegram channel promotion', link_ph: 'Channel/group link', qty: 'Quantity', order: 'Order', cost: 'Cost', guarantee: '365-day guarantee', done: 'Order placed!' },
  }[lang]

  if (success) {
    return (
      <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
        <div style={{ fontSize: 64 }}>✅</div>
        <div style={{ fontWeight: 800, fontSize: 20 }}>{label.done}</div>
        <div style={{ color: 'var(--muted)', fontSize: 14 }}>#{success.order_id} · ⭐{success.stars_spent}</div>
        <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={() => setSuccess(null)}>
          {lang === 'ru' ? 'Ещё заказ' : lang === 'ua' ? 'Ще замовлення' : 'New order'}
        </button>
      </div>
    )
  }

  return (
    <div className="page">
      <h1 style={{ margin: '0 0 4px' }}>⚡ {label.title}</h1>
      <p className="muted" style={{ fontSize: 13, marginBottom: 20 }}>{label.desc}</p>

      {!svc ? (
        <div className="card"><div className="skeleton" style={{ height: 80 }} /></div>
      ) : (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
            <div style={{ fontSize: 40 }}>👥</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 16 }}>{svc.title}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{svc.description}</div>
              <div style={{ fontSize: 12, color: '#4cff8f', marginTop: 2 }}>✅ {label.guarantee}</div>
            </div>
            <div style={{ fontWeight: 800, fontSize: 18, color: 'var(--orange)', whiteSpace: 'nowrap' }}>
              ⭐{svc.price_per_100_stars}<span style={{ fontWeight: 400, fontSize: 12, color: 'var(--muted)' }}>/100</span>
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>
              {label.link_ph}
            </label>
            <input
              type="text"
              placeholder="https://t.me/..."
              value={link}
              onChange={e => setLink(e.target.value)}
              style={{
                width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
                borderRadius: 12, padding: '11px 14px', color: 'var(--text)', fontSize: 14, boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginBottom: 6 }}>
              {label.qty}: <b style={{ color: 'var(--text)' }}>{quantity}</b>
            </label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {[100, 200, 500, 1000, 5000].map(q => (
                <button
                  key={q}
                  onClick={() => setQuantity(q)}
                  style={{
                    padding: '7px 14px', borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: 'pointer',
                    background: quantity === q ? 'var(--orange)' : 'var(--card2)',
                    color: quantity === q ? '#fff' : 'var(--text)',
                    border: '1px solid ' + (quantity === q ? 'var(--orange)' : 'var(--border)'),
                  }}
                >{q}</button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ color: 'var(--muted)', fontSize: 14 }}>{label.cost}:</span>
            <span style={{ fontWeight: 800, fontSize: 22, color: 'var(--orange)' }}>⭐{priceStars}</span>
          </div>

          {error && <div style={{ color: '#ff4444', fontSize: 13, marginBottom: 10 }}>❌ {error}</div>}

          <button
            className="btn btn-primary"
            style={{ width: '100%' }}
            disabled={!canBuy}
            onClick={submit}
          >
            {loading ? '⏳...' : `${label.order} — ⭐${priceStars}`}
          </button>
        </div>
      )}
    </div>
  )
}
