import { useState, useEffect } from 'react'
import { api, type Item, type BuyResult, type Me } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang; me: Me | null }

type View = 'list' | 'buying' | 'success' | 'error'

function localPrice(usd: number, lang: Lang, me: Me | null): string {
  const base = `$${usd.toFixed(2)}`
  if (!me) return base
  if (lang === 'ua' && me.rate_uah) return `${base} (~${Math.round(usd * me.rate_uah)}₴)`
  if (lang === 'ru' && me.rate_rub) return `${base} (~${Math.round(usd * me.rate_rub)}₽)`
  return base
}

export default function Shop({ lang, me }: Props) {
  const T = getT(lang)
  const [view, setView]     = useState<View>('list')
  const [items, setItems]   = useState<Item[]>([])
  const [result, setResult] = useState<BuyResult | null>(null)
  const [errMsg, setErr]    = useState('')
  const [copied, setCopied] = useState<'phone' | 'code' | ''>('')

  useEffect(() => {
    api.shop('us').catch(() => []).then(setItems)
  }, [])

  async function buy(item: Item) {
    setView('buying')
    try {
      const res = await api.buy(item.item_id, item.price, 'us')
      setResult(res)
      setView('success')
    } catch (e: any) {
      setErr(e.message ?? T.buy_error)
      setView('error')
    }
  }

  function copy(text: string, which: 'phone' | 'code') {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(which)
      setTimeout(() => setCopied(''), 2000)
    })
  }

  if (view === 'list') return (
    <div className="page">
      <h1>{T.usa_accounts}</h1>
      {items.length === 0 ? (
        <>
          <div className="card"><div className="skeleton" style={{ height: 56 }} /></div>
          <div className="card"><div className="skeleton" style={{ height: 56 }} /></div>
          <div className="card"><div className="skeleton" style={{ height: 56 }} /></div>
        </>
      ) : (
        items.map(item => (
          <div key={item.item_id} className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{item.title || 'TG account'}</div>
              {item.reg_date && <div className="muted" style={{ fontSize: 12 }}>{item.reg_date}</div>}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ fontWeight: 700, color: 'var(--orange)', fontSize: 15, marginBottom: 4 }}>
                {localPrice(item.price, lang, me)}
              </div>
              <button
                className="btn btn-primary"
                style={{ padding: '6px 14px', width: 'auto', fontSize: 13 }}
                onClick={() => buy(item)}
              >
                {T.buy}
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  )

  if (view === 'buying') return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
      <div style={{ fontSize: 48 }}>🦎</div>
      <p style={{ fontWeight: 600, fontSize: 16 }}>{T.buying}</p>
    </div>
  )

  if (view === 'success' && result) return (
    <div className="page">
      <div className="card" style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 36, marginBottom: 6 }}>✅</div>
        <div style={{ fontWeight: 700, fontSize: 15 }}>
          {T.order_num} #{String(result.order_id).padStart(5, '0')}
        </div>
      </div>

      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>{T.your_phone}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{ flex: 1, fontSize: 18, fontWeight: 700 }}>{result.phone}</code>
          <button className="btn btn-secondary" style={{ width: 'auto', padding: '7px 12px' }}
            onClick={() => copy(result.phone, 'phone')}>
            {copied === 'phone' ? T.copied : T.copy}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>{T.your_code}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{ flex: 1, fontSize: 22, fontWeight: 700, letterSpacing: 3 }}>{result.code}</code>
          <button className="btn btn-secondary" style={{ width: 'auto', padding: '7px 12px' }}
            onClick={() => copy(result.code, 'code')}>
            {copied === 'code' ? T.copied : T.copy}
          </button>
        </div>
      </div>

      <div className="card" style={{ background: 'var(--sand)' }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>📋 {T.instruction}</div>
        <ol style={{ paddingLeft: 18, lineHeight: 2, margin: 0 }}>
          <li>{T.step1} <a href="https://justrunmy.app/panel/add" target="_blank" rel="noreferrer" style={{ color: 'var(--orange)' }}>justrunmy.app</a></li>
          <li>{T.step2}: <code>{result.phone}</code></li>
          <li>{T.step3}: <code>{result.code}</code></li>
          <li>{T.step4}</li>
        </ol>
        <p style={{ marginTop: 10, color: 'var(--brown)', fontSize: 12 }}>{T.warning}</p>
      </div>

      <button className="btn btn-secondary" onClick={() => { setResult(null); setView('list') }}>
        {T.back}
      </button>
    </div>
  )

  if (view === 'error') return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
      <div style={{ fontSize: 48 }}>❌</div>
      <p style={{ fontWeight: 600 }}>{errMsg || T.buy_error}</p>
      <button className="btn btn-secondary" onClick={() => setView('list')}>{T.back}</button>
    </div>
  )

  return null
}
