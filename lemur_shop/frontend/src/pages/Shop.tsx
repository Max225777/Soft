import { useState, useEffect } from 'react'
import { api, type Category, type BuyResult, type Me } from '../api'
import { getT, type Lang } from '../i18n'

interface Props { lang: Lang; me: Me | null; onGoToBalance: () => void }

type View = 'list' | 'buying' | 'success' | 'error'

function localPrice(usd: number, lang: Lang, me: Me | null): string {
  const base = `$${usd.toFixed(2)}`
  if (!me) return base
  if (lang === 'ua' && me.rate_uah) return `${base} (~${Math.round(usd * me.rate_uah)}₴)`
  if (lang === 'ru' && me.rate_rub) return `${base} (~${Math.round(usd * me.rate_rub)}₽)`
  return base
}

export default function Shop({ lang, me, onGoToBalance }: Props) {
  const T = getT(lang)
  const [view, setView]     = useState<View>('list')
  const [cats, setCats]     = useState<Category[]>([])
  const [result, setResult] = useState<BuyResult | null>(null)
  const [errMsg, setErr]    = useState('')
  const [copied, setCopied] = useState<'phone' | 'code' | ''>('')

  useEffect(() => {
    api.categories().catch(() => []).then(setCats)
  }, [])

  async function buy(cat: Category) {
    setView('buying')
    try {
      const res = await api.buy(cat.category)
      setResult(res)
      setView('success')
    } catch (e: any) {
      if (e.message === 'insufficient_balance') {
        setView('list')
        onGoToBalance()
        return
      }
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
      <h1>{T.shop}</h1>
      {cats.length === 0 ? (
        <>
          <div className="card"><div className="skeleton" style={{ height: 60 }} /></div>
          <div className="card"><div className="skeleton" style={{ height: 60 }} /></div>
        </>
      ) : (
        cats.map(cat => (
          <div key={cat.category} className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 32, flexShrink: 0 }}>{cat.flag}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{cat.title}</div>
              <div style={{ fontWeight: 700, color: 'var(--orange)', fontSize: 14, marginTop: 2 }}>
                {localPrice(cat.price_usd, lang, me)}
              </div>
            </div>
            <button
              className="btn btn-primary"
              style={{ padding: '8px 16px', width: 'auto', fontSize: 14 }}
              onClick={() => buy(cat)}
            >
              {T.buy}
            </button>
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
