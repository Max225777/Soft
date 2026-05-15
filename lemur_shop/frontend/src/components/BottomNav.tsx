import type { Lang } from '../i18n'
import { getT } from '../i18n'

type Tab = 'shop' | 'profile' | 'balance'

interface Props { active: Tab; onChange(t: Tab): void; lang: Lang }

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
}

export default function BottomNav({ active, onChange, lang }: Props) {
  const T = getT(lang)
  const tabs: Tab[] = ['shop', 'profile', 'balance']
  const labels: Record<Tab, string> = {
    shop: T.shop,
    profile: T.profile,
    balance: T.balance_tab,
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
