import type { Lang } from '../i18n'
import { getT } from '../i18n'

export type Tab = 'shop' | 'profile' | 'orders' | 'balance' | 'referral' | 'admin' | 'fortune'

interface Props {
  active: Tab
  onChange(t: Tab): void
  lang: Lang
  isAdmin?: boolean
}

const shopIcon = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="28" height="28">
    <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/>
    <line x1="3" y1="6" x2="21" y2="6"/>
    <path d="M16 10a4 4 0 01-8 0"/>
  </svg>
)

const icons: Record<Exclude<Tab, 'shop'>, JSX.Element> = {
  fortune: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
    </svg>
  ),
  profile: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
      <circle cx="12" cy="7" r="4"/>
    </svg>
  ),
  orders: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
      <rect x="9" y="3" width="6" height="4" rx="1"/>
      <line x1="9" y1="12" x2="15" y2="12"/>
      <line x1="9" y1="16" x2="13" y2="16"/>
    </svg>
  ),
  balance: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="5" width="20" height="14" rx="2"/>
      <line x1="2" y1="10" x2="22" y2="10"/>
    </svg>
  ),
  referral: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path d="M23 21v-2a4 4 0 00-3-3.87"/>
      <path d="M16 3.13a4 4 0 010 7.75"/>
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

  const labels: Record<Tab, string> = {
    shop:     'Магазин',
    fortune:  lang === 'en' ? 'Mini-games' : 'Мін-ігри',
    profile:  lang === 'ru' ? 'Профиль' : lang === 'ua' ? 'Профіль' : 'Profile',
    orders:   lang === 'ru' ? 'Заказы' : lang === 'ua' ? 'Замовлення' : 'Orders',
    balance:  lang === 'ru' ? 'Баланс' : lang === 'ua' ? 'Баланс' : 'Balance',
    referral: lang === 'ru' ? 'Рефералы' : lang === 'ua' ? 'Реферали' : 'Referrals',
    admin:    'Адмін',
  }

  const leftTabs: Tab[] = ['profile', 'orders']
  const rightTabs: Tab[] = isAdmin ? ['fortune', 'balance', 'admin'] : ['balance', 'referral']

  return (
    <nav className="nav" style={{ overflow: 'visible', alignItems: 'stretch', gap: 0 }}>

      {leftTabs.map(tab => (
        <button
          key={tab}
          className={`nav-item ${active === tab ? 'active' : ''}`}
          style={{ flex: 1 }}
          onClick={() => onChange(tab)}
        >
          {icons[tab as Exclude<Tab, 'shop'>]}
          <span style={{ fontSize: 10 }}>{labels[tab]}</span>
        </button>
      ))}

      {/* Центр — FAB */}
      <div style={{ flex: 1.4, position: 'relative', overflow: 'visible' }}>
        <button
          onClick={() => onChange('shop')}
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 68, height: 68,
            borderRadius: '50%',
            background: active === 'shop'
              ? 'linear-gradient(135deg, #FF8C42, #FF5500)'
              : 'linear-gradient(135deg, #FF6B2B, #E8530A)',
            border: active === 'shop'
              ? '2.5px solid rgba(255,255,255,.4)'
              : '2.5px solid rgba(255,107,43,.25)',
            boxShadow: active === 'shop'
              ? '0 5px 22px rgba(255,107,43,.8)'
              : '0 3px 16px rgba(255,107,43,.5)',
            cursor: 'pointer',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 2,
            color: 'white',
            transition: 'all .2s',
            flexShrink: 0,
          }}
        >
          {shopIcon}
          <span style={{
            fontSize: 10, fontWeight: 700,
            color: 'rgba(255,255,255,.95)',
            lineHeight: 1,
            userSelect: 'none',
            letterSpacing: 0.2,
          }}>
            {labels.shop}
          </span>
        </button>
      </div>

      {rightTabs.map(tab => (
        <button
          key={tab}
          className={`nav-item ${active === tab ? 'active' : ''}`}
          style={{ flex: 1 }}
          onClick={() => onChange(tab)}
        >
          {icons[tab as Exclude<Tab, 'shop'>]}
          <span style={{ fontSize: 10 }}>{labels[tab]}</span>
        </button>
      ))}

    </nav>
  )
}
