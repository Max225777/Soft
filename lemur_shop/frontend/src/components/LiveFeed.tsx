import { useState, useEffect, useRef } from 'react'
import { api, type LiveFeedItem } from '../api'
import type { Lang } from '../i18n'

const TITLE: Record<Lang, string> = {
  ru: 'Покупки в реальном времени',
  ua: 'Покупки в реальному часі',
  en: 'Live purchases',
}
const BOUGHT: Record<Lang, string> = {
  ru: 'купил', ua: 'купив', en: 'bought',
}

const VISIBLE = 3      // скільки рядків показуємо одночасно
const ROTATE_MS = 3000 // як часто «прокручуємо» стрічку

function timeAgo(iso: string | null, lang: Lang): string {
  if (!iso) return ''
  const diff = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  const m = Math.floor(diff / 60)
  const h = Math.floor(m / 60)
  const d = Math.floor(h / 24)
  if (lang === 'en') {
    if (diff < 60) return 'just now'
    if (m < 60) return `${m}m ago`
    if (h < 24) return `${h}h ago`
    return `${d}d ago`
  }
  if (diff < 60) return lang === 'ua' ? 'щойно' : 'только что'
  if (m < 60) return `${m} ${lang === 'ua' ? 'хв' : 'мин'} назад`
  if (h < 24) return `${h} ${lang === 'ua' ? 'год' : 'ч'} назад`
  return `${d} ${lang === 'ua' ? 'дн' : 'дн'} назад`
}

export default function LiveFeed({ lang }: { lang: Lang }) {
  const [items, setItems] = useState<LiveFeedItem[]>([])
  const [offset, setOffset] = useState(0)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let alive = true
    const load = () => api.liveFeed().then(d => { if (alive) setItems(d) }).catch(() => {})
    load()
    const poll = setInterval(load, 15000)
    return () => { alive = false; clearInterval(poll) }
  }, [])

  useEffect(() => {
    if (items.length <= VISIBLE) return
    timer.current = setInterval(() => setOffset(o => (o + 1) % items.length), ROTATE_MS)
    return () => { if (timer.current) clearInterval(timer.current) }
  }, [items.length])

  if (items.length === 0) return null

  // вікно з VISIBLE елементів, що циклічно зсувається
  const window = Array.from({ length: Math.min(VISIBLE, items.length) }, (_, i) => items[(offset + i) % items.length])

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 18, padding: '12px 14px', marginBottom: 12, overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
        <span style={{ position: 'relative', display: 'inline-flex', width: 8, height: 8 }}>
          <span style={{
            position: 'absolute', inset: 0, borderRadius: '50%',
            background: '#33D07A', animation: 'lf-ping 1.6s ease-out infinite',
          }} />
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#33D07A' }} />
        </span>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text2)', letterSpacing: .3 }}>
          {TITLE[lang]}
        </span>
      </div>

      <style>{`
        @keyframes lf-ping { 0%{transform:scale(1);opacity:.7} 80%,100%{transform:scale(2.6);opacity:0} }
        @keyframes lf-in { from{opacity:0;transform:translateY(-6px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {window.map((it, i) => (
          <div
            key={`${offset}-${i}`}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 10px', borderRadius: 12,
              background: 'var(--card2)', border: '1px solid var(--border)',
              animation: i === 0 ? 'lf-in .35s ease' : undefined,
            }}
          >
            <span style={{ fontSize: 20, flexShrink: 0, lineHeight: 1 }}>{it.flag}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text)', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                <span style={{ color: '#7DB4FF' }}>{it.has_username ? '@' : ''}{it.user_display}</span>
                <span style={{ color: 'var(--muted)', fontWeight: 400 }}> {BOUGHT[lang]} </span>
                <code style={{
                  background: 'none', border: 'none', padding: 0,
                  color: 'var(--text2)', fontSize: 12, letterSpacing: .5,
                }}>{it.phone_masked}</code>
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
                {timeAgo(it.created_at, lang)}
              </div>
            </div>
            <div style={{ fontWeight: 800, fontSize: 13, color: 'var(--orange2)', flexShrink: 0 }}>
              ⭐{it.amount_stars}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
