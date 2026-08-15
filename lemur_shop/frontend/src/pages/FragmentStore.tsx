import { useState, useEffect } from 'react'
import { api, type Me, type FragmentPrices } from '../api'
import type { Lang } from '../i18n'

interface Props { lang: Lang; me: Me | null; onBuy?: () => void; onBack: () => void }

interface Strings {
  title: string; sub: string; stars: string; premium: string
  recipient: string; recipientPh: string; chooseQty: string; custom: string
  chooseDur: string; months: string; balance: string; pay: string
  notEnough: string; enterUser: string; success: string; successStars: string
  successPrem: string; err: string; errUser: string; errFrag: string
  price: string; profitInfo: string
}

const LMAP: Record<Lang, Strings> = {
  ru: {
    title: 'Stars и Premium', sub: 'Прямое пополнение через Fragment',
    stars: 'Telegram Stars', premium: 'Telegram Premium',
    recipient: 'Юзернейм получателя', recipientPh: 'например @durov',
    chooseQty: 'Выберите количество', custom: 'Своё количество (от 50)',
    chooseDur: 'Выберите срок', months: 'мес',
    balance: 'Баланс', pay: 'Купить', notEnough: 'Недостаточно баланса',
    enterUser: 'Введите юзернейм получателя',
    success: 'Отправлено!', successStars: '⭐ зачислятся получателю автоматически',
    successPrem: 'Premium активируется получателю автоматически',
    err: 'Ошибка', errUser: 'Неверный юзернейм', errFrag: 'Не удалось выполнить — средства возвращены',
    price: 'Цена', profitInfo: 'Оплата с баланса магазина',
  },
  ua: {
    title: 'Stars і Premium', sub: 'Пряме поповнення через Fragment',
    stars: 'Telegram Stars', premium: 'Telegram Premium',
    recipient: 'Юзернейм отримувача', recipientPh: 'наприклад @durov',
    chooseQty: 'Оберіть кількість', custom: 'Своя кількість (від 50)',
    chooseDur: 'Оберіть термін', months: 'міс',
    balance: 'Баланс', pay: 'Купити', notEnough: 'Недостатньо балансу',
    enterUser: 'Введіть юзернейм отримувача',
    success: 'Надіслано!', successStars: '⭐ зарахуються отримувачу автоматично',
    successPrem: 'Premium активується отримувачу автоматично',
    err: 'Помилка', errUser: 'Невірний юзернейм', errFrag: 'Не вдалося виконати — кошти повернено',
    price: 'Ціна', profitInfo: 'Оплата з балансу магазину',
  },
  en: {
    title: 'Stars & Premium', sub: 'Direct top-up via Fragment',
    stars: 'Telegram Stars', premium: 'Telegram Premium',
    recipient: 'Recipient username', recipientPh: 'e.g. @durov',
    chooseQty: 'Choose amount', custom: 'Custom amount (from 50)',
    chooseDur: 'Choose duration', months: 'mo',
    balance: 'Balance', pay: 'Buy', notEnough: 'Not enough balance',
    enterUser: 'Enter recipient username',
    success: 'Sent!', successStars: '⭐ will be credited automatically',
    successPrem: 'Premium activates for the recipient automatically',
    err: 'Error', errUser: 'Invalid username', errFrag: 'Failed — funds refunded',
    price: 'Price', profitInfo: 'Paid from shop balance',
  },
}

export default function FragmentStore({ lang, me, onBuy, onBack }: Props) {
  const L = LMAP[lang] ?? LMAP.ru
  const [prices, setPrices] = useState<FragmentPrices | null>(null)
  const [kind, setKind] = useState<'stars' | 'premium'>('stars')
  const [username, setUsername] = useState('')
  const [qty, setQty] = useState(500)
  const [customQty, setCustomQty] = useState('')
  const [months, setMonths] = useState(3)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<{ label: string; recipient: string; dry: boolean } | null>(null)

  useEffect(() => { api.fragmentPrices().then(setPrices).catch(() => {}) }, [])

  const balance = me?.balance_stars ?? 0
  const rate = prices?.rate_rub ?? me?.rate_rub ?? 0
  const starUsd = prices?.star_display_usd ?? 0.013

  const fmt = (n: number) => Math.round(n).toLocaleString('ru-RU')
  const rub = (usd: number) => fmt(usd * rate)

  function starsSellUsd(n: number): number {
    if (!prices) return 0
    return n * prices.star_cost_usd * (1 + prices.stars_margin_pct / 100) + prices.stars_fee_usd
  }
  const effQty = customQty ? Math.max(0, parseInt(customQty) || 0) : qty
  let sellUsd = 0
  if (kind === 'stars') {
    sellUsd = starsSellUsd(effQty)
  } else {
    sellUsd = prices?.premium_options.find(o => o.months === months)?.sell_usd ?? 0
  }
  const priceStars = starUsd ? Math.round(sellUsd / starUsd) : 0
  const enough = balance >= priceStars
  const validUser = username.trim().replace('@', '').length >= 3
  const validQty = kind === 'premium' || effQty >= 50

  async function submit() {
    setError(null)
    if (!validUser) { setError(L.errUser); return }
    if (!validQty) { setError(L.err); return }
    if (!enough) { setError(L.notEnough); return }
    setLoading(true)
    try {
      const res = await api.fragmentBuy(kind, username.trim(), kind === 'stars' ? effQty : 0, kind === 'premium' ? months : 0)
      setDone({ label: res.label, recipient: res.recipient, dry: res.dry_run })
      onBuy?.()
    } catch (e: any) {
      const msg = String(e?.message || '')
      setError(msg.includes('insufficient') ? L.notEnough
        : msg.includes('username') ? L.errUser
        : L.errFrag)
    } finally { setLoading(false) }
  }

  const card: React.CSSProperties = {
    background: 'var(--card)', border: '1px solid var(--border)',
    borderRadius: 16, padding: 16, marginBottom: 12,
  }
  const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--card2)', border: '1px solid var(--border)',
    borderRadius: 12, padding: '12px 14px', color: 'var(--text)', fontSize: 15,
    outline: 'none', boxSizing: 'border-box',
  }
  const pkgBtn = (active: boolean): React.CSSProperties => ({
    background: active ? 'rgba(255,184,48,.14)' : 'var(--card2)',
    border: `1px solid ${active ? 'rgba(255,184,48,.5)' : 'var(--border)'}`,
    borderRadius: 12, padding: '12px 8px', cursor: 'pointer',
    color: active ? '#FFB830' : 'var(--text)', fontWeight: 700, fontSize: 14,
    display: 'flex', flexDirection: 'column', gap: 3, alignItems: 'center',
  })

  if (done) {
    return (
      <div className="page" style={{ paddingTop: 12 }}>
        <div style={{ ...card, textAlign: 'center', padding: '32px 20px', marginTop: 40 }}>
          <div style={{ fontSize: 52, marginBottom: 10 }}>{done.dry ? '🧪' : '✅'}</div>
          <div style={{ fontWeight: 800, fontSize: 20, marginBottom: 8 }}>{L.success}</div>
          <div style={{ color: 'var(--muted)', fontSize: 14, marginBottom: 4 }}>
            <b>{done.label}</b> → @{done.recipient}
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 13 }}>
            {kind === 'stars' ? L.successStars : L.successPrem}
          </div>
          {done.dry && <div style={{ color: '#ffb347', fontSize: 12, marginTop: 10 }}>DRY-RUN — тестовый режим, реально не оплачено</div>}
          <button className="btn btn-primary" style={{ marginTop: 20, width: '100%' }}
            onClick={() => { setDone(null); setUsername('') }}>OK</button>
        </div>
      </div>
    )
  }

  return (
    <div className="page" style={{ paddingTop: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <button onClick={onBack} style={{
          width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'var(--card2)', border: '1px solid var(--border)', cursor: 'pointer', fontSize: 20, color: 'var(--text2)', flexShrink: 0,
        }}>‹</button>
        <div>
          <h1 style={{ margin: 0, fontSize: 20 }}>{L.title}</h1>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>{L.sub}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        {(['stars', 'premium'] as const).map(k => (
          <button key={k} onClick={() => setKind(k)} style={{
            flex: 1, padding: '12px', borderRadius: 12, cursor: 'pointer', fontWeight: 700, fontSize: 14,
            background: kind === k ? 'linear-gradient(135deg,#FFB830,#e09000)' : 'var(--card2)',
            color: kind === k ? '#1a1200' : 'var(--text)',
            border: `1px solid ${kind === k ? 'transparent' : 'var(--border)'}`,
          }}>{k === 'stars' ? `⭐ ${L.stars}` : `⭐ ${L.premium}`}</button>
        ))}
      </div>

      <div style={card}>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{L.recipient}</div>
        <input style={inputStyle} placeholder={L.recipientPh} value={username}
          onChange={e => setUsername(e.target.value)} autoCapitalize="off" autoCorrect="off" />
      </div>

      {kind === 'stars' && (
        <div style={card}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10 }}>{L.chooseQty}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
            {(prices?.stars_packages ?? []).map(p => (
              <button key={p.qty} style={pkgBtn(!customQty && qty === p.qty)}
                onClick={() => { setQty(p.qty!); setCustomQty('') }}>
                <span>⭐{fmt(p.qty!)}</span>
                <span style={{ fontSize: 12, fontWeight: 800 }}>{p.sell_rub} ₽</span>
              </button>
            ))}
          </div>
          <input style={inputStyle} type="number" min={50} placeholder={L.custom}
            value={customQty} onChange={e => setCustomQty(e.target.value)} />
        </div>
      )}

      {kind === 'premium' && (
        <div style={card}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10 }}>{L.chooseDur}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(prices?.premium_options ?? []).map(o => (
              <button key={o.months} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '14px 16px', borderRadius: 12, cursor: 'pointer',
                background: months === o.months ? 'rgba(255,184,48,.12)' : 'var(--card2)',
                border: `1px solid ${months === o.months ? 'rgba(255,184,48,.5)' : 'var(--border)'}`,
                color: 'var(--text)',
              }} onClick={() => setMonths(o.months!)}>
                <span style={{ fontWeight: 700 }}>{o.months} {L.months}</span>
                <span style={{ fontWeight: 800, color: months === o.months ? '#FFB830' : 'var(--text)' }}>{o.sell_rub} ₽</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ ...card, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>{L.price}</div>
          <div style={{ fontWeight: 800, fontSize: 20 }}>{rub(sellUsd)} ₽ <span style={{ fontSize: 13, color: 'var(--muted)', fontWeight: 500 }}>(⭐{fmt(priceStars)})</span></div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>{L.balance}</div>
          <div style={{ fontWeight: 700, fontSize: 15, color: enough ? 'var(--text)' : 'var(--red)' }}>⭐{fmt(balance)}</div>
        </div>
      </div>

      {error && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 10, textAlign: 'center' }}>❌ {error}</div>}

      <button className="btn btn-primary" disabled={loading || !validUser || !validQty || !enough}
        onClick={submit}
        style={{ width: '100%', padding: 14, fontSize: 15,
          background: 'linear-gradient(135deg,#FFB830,#e09000)', opacity: (loading || !enough || !validUser) ? 0.55 : 1 }}>
        {loading ? '⏳...' : !validUser ? L.enterUser : !enough ? L.notEnough : `${L.pay} · ${rub(sellUsd)} ₽`}
      </button>
      <div style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', marginTop: 8 }}>{L.profitInfo}</div>
    </div>
  )
}
