import type { Lang } from '../i18n'
import { getT } from '../i18n'

export type Tab = 'shop' | 'profile' | 'balance' | 'admin'

interface Props {
  active: Tab
  onChange(t: Tab): void
  lang: Lang
  isAdmin?: boolean
}

const shopIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" width="24" height="24">
    <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/>
    <line x1="3" y1="6" x2="21" y2="6"/>
    <path d="M16 10a4 4 0 01-8 0"/>
  </svg>
)

const icons: Record<Exclude<Tab, 'shop'>, JSX.Element> = {
  profile: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  ),
  balance: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="5" width="20" height="14" rx="2"/>
      <line x1="2" y1="10" x2="22" y2="10"/>
    </svg>
  ),
  admin: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3"/>
      <path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2"/>
    </svg>
  ),
}

export default function BottomNav({ active, onChange, lang, isAdmin }: Props) {
  const T = getT(lang)

  const leftTabs:  Tab[] = ['profile']
  const rightTabs: Tab[] = isAdmin ? ['balance', 'admin'] : ['balance']

  const strip = (s: string) => s.replace(/^[^\p{L}\d]+/u, '').trim()

  const labels: Record<Tab, string> = {
    shop:    'Магазин',
    profile: strip(T.profile),
    balance: 'Баланс/Реф',
    admin:   'Адмін',
  }

  return (
    <nav className="nav" style={{ overflow: 'visible', alignItems: 'stretch', gap: 0 }}>

      {/* Ліво */}
      {leftTabs.map(tab => (
        <button
          key={tab}
          className={`nav-item ${active === tab ? 'active' : ''}`}
          style={{ flex: 1 }}
          onClick={() => onChange(tab)}
        >
          {icons[tab as Exclude<Tab, 'shop'>]}
          {labels[tab]}
        </button>
      ))}

      {/* Центр — FAB */}
      <div style={{ flex: 1.1, position: 'relative', overflow: 'visible' }}>
        <div style={{
          position: 'absolute',
          left: '50%',
          top: '50%',
          transform: 'translate(-50%, calc(-50% - 5px))',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
        }}>
          <button
            onClick={() => onChange('shop')}
            style={{
              width: 52, height: 52,
              borderRadius: '50%',
              background: active === 'shop'
                ? 'linear-gradient(135deg, #FF8C42, #FF5500)'
                : 'linear-gradient(135deg, #FF6B2B, #E8530A)',
              border: active === 'shop'
                ? '2px solid rgba(255,255,255,.35)'
                : '2px solid rgba(255,107,43,.2)',
              boxShadow: active === 'shop'
                ? '0 4px 20px rgba(255,107,43,.75)'
                : '0 3px 14px rgba(255,107,43,.45)',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'white',
              transition: 'all .2s',
              flexShrink: 0,
            }}
          >
            {shopIcon}
          </button>
          <span style={{
            fontSize: 11, fontWeight: active === 'shop' ? 700 : 500,
            color: active === 'shop' ? 'var(--orange)' : 'var(--muted)',
            transition: 'color .18s',
            userSelect: 'none',
            whiteSpace: 'nowrap',
          }}>
            {labels['shop']}
          </span>
        </div>
      </div>

      {/* Право */}
      {rightTabs.map(tab => (
        <button
          key={tab}
          className={`nav-item ${active === tab ? 'active' : ''}`}
          style={{ flex: 1 }}
          onClick={() => onChange(tab)}
        >
          {icons[tab as Exclude<Tab, 'shop'>]}
          {labels[tab]}
        </button>
      ))}

    </nav>
  )
}
