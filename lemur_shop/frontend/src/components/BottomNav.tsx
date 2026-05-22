import type { Lang } from '../i18n'
import { getT } from '../i18n'

export type Tab = 'shop' | 'profile' | 'balance' | 'admin'

interface Props { active: Tab; onChange(t: Tab): void; lang: Lang; isAdmin?: boolean }

const icons: Record<Tab, JSX.Element> = {
  shop: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/>
      <line x1="3" y1="6" x2="21" y2="6"/>
      <path d="M16 10a4 4 0 01-8 0"/>
    </svg>
  ),
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
  wheel: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10"/>
      <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none"/>
      <line x1="12" y1="2"  x2="12" y2="6"/>
      <line x1="12" y1="18" x2="12" y2="22"/>
      <line x1="2"  y1="12" x2="6"  y2="12"/>
      <line x1="18" y1="12" x2="22" y2="12"/>
      <line x1="5.5"  y1="5.5"  x2="8.4"  y2="8.4"/>
      <line x1="15.6" y1="15.6" x2="18.5" y2="18.5"/>
      <line x1="18.5" y1="5.5"  x2="15.6" y2="8.4"/>
      <line x1="8.4"  y1="15.6" x2="5.5"  y2="18.5"/>
    </svg>
  ),
}

export default function BottomNav({ active, onChange, lang, isAdmin }: Props) {
  const T = getT(lang)
  const tabs: Tab[] = isAdmin
    ? ['shop', 'balance', 'profile', 'admin']
    : ['shop', 'balance', 'profile']
  const labels: Record<Tab, string> = {
    shop:    T.shop,
    profile: T.profile,
    balance: T.balance_tab,
    admin:   '⚙️ Адмін',
  }
  return (
    <nav className="nav">
      {tabs.map(tab => (
        <button
          key={tab}
          className={`nav-item ${active === tab ? 'active' : ''}`}
          onClick={() => onChange(tab)}
        >
          {icons[tab]}
          {labels[tab].replace(/^[^ ]+ /, '')}
        </button>
      ))}
    </nav>
  )
}
