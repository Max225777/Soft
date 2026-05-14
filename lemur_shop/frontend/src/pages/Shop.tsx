import { useState, useEffect } from 'react'
import { api, type Item, type BuyResult } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang }

type View = 'categories' | 'list' | 'buying' | 'success' | 'error'

const CATEGORIES = [{ id: 'us', emoji: '🇺🇸', label_ua: 'USA акаунти', label_ru: 'USA аккаунты' }]

export default function Shop({ lang }: Props) {
  const T = getT(lang)
  const [view, setView]       = useState<View>('categories')
  const [category, setCat]    = useState('')
  const [items, setItems]     = useState<Item[]>([])
  const [result, setResult]   = useState<BuyResult | null>(null)
  const [errMsg, setErr]      = useState('')
  const [copied, setCopied]   = useState<'phone'|'code'|''>('')

  async function openCategory(cat: string) {
    setCat(cat)
    setView('list')
    setItems([])
    const data = await api.shop(cat).catch(() => [])
    setItems(data)
  }

  async function buy(item: Item) {
    setView('buying')
    try {
      const res = await api.buy(item.item_id, item.price, category)
      setResult(res)
      setView('success')
    } catch (e: any) {
      setErr(e.message ?? T.buy_error)
      setView('error')
    }
  }

  function copy(text: string, which: 'phone'|'code') {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(which)
      setTimeout(() => setCopied(''), 2000)
    })
  }

  if (view === 'categories') return (
    <div className="page">
      <h1>🛍 {T.shop.replace(/^[^ ]+ /, '')}</h1>
      <p className="muted" style={{ marginBottom: 16 }}>Оберіть категорію</p>
      {CATEGORIES.map(c => (
        <div key={c.id} className="card" style={{ cursor: 'pointer' }} onClick={() => openCategory(c.id)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 32 }}>{c.emoji}</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: 16 }}>
                {lang === 'ua' ? c.label_ua : c.label_ru}
              </div>
              <div className="muted">Telegram autoreg</div>
            </div>
            <span style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: 20 }}>›</span>
          </div>
        </div>
      ))}
    </div>
  )

  if (view === 'list') return (
    <div className="page">
      <button className="btn btn-secondary" style={{ marginBottom: 16 }} onClick={() => setView('categories')}>
        {T.back}
      </button>
      {items.length === 0 ? (
        <div className="card">
          <div className="skeleton" style={{ height: 60, marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 60, marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 60 }} />
        </div>
      ) : items.length === 0 ? (
        <p>{T.no_items}</p>
      ) : (
        items.map(item => (
          <div key={item.item_id} className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{item.title}</div>
              {item.reg_date && <div className="muted">{item.reg_date}</div>}
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 700, color: 'var(--orange)', fontSize: 16 }}>${item.price.toFixed(2)}</div>
              <button className="btn btn-primary" style={{ marginTop: 6, padding: '6px 14px', width: 'auto' }}
                onClick={() => buy(item)}>
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
      <div className="card" style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
        <h2 style={{ marginBottom: 4 }}>{T.order_id} #{result.order_id}</h2>
      </div>

      <div className="card">
        <div className="muted" style={{ marginBottom: 6 }}>{T.your_phone}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{ flex: 1, fontSize: 18, fontWeight: 700 }}>{result.phone}</code>
          <button className="btn btn-secondary" style={{ width: 'auto', padding: '8px 12px' }}
            onClick={() => copy(result.phone, 'phone')}>
            {copied === 'phone' ? T.copied : T.copy}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="muted" style={{ marginBottom: 6 }}>{T.your_code}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <code style={{ flex: 1, fontSize: 24, fontWeight: 700, letterSpacing: 4 }}>{result.code}</code>
          <button className="btn btn-secondary" style={{ width: 'auto', padding: '8px 12px' }}
            onClick={() => copy(result.code, 'code')}>
            {copied === 'code' ? T.copied : T.copy}
          </button>
        </div>
      </div>

      <div className="card" style={{ background: 'var(--sand)' }}>
        <h2>📋 {T.instruction}</h2>
        <ol style={{ paddingLeft: 20, lineHeight: 2 }}>
          <li>{T.step1} <a href="https://justrunmy.app/panel/add" target="_blank" rel="noreferrer" style={{ color: 'var(--orange)' }}>justrunmy.app/panel/add</a></li>
          <li>{T.step2}: <code>{result.phone}</code></li>
          <li>{T.step3}: <code>{result.code}</code></li>
          <li>{T.step4}</li>
        </ol>
        <p style={{ marginTop: 12, color: 'var(--brown)', fontSize: 13 }}>{T.warning}</p>
      </div>

      <button className="btn btn-secondary" onClick={() => { setResult(null); setView('categories') }}>
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
