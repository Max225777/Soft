import { useState, useEffect } from 'react'
import { api, type Me } from './api'
import BottomNav from './components/BottomNav'
import Shop from './pages/Shop'
import Profile from './pages/Profile'
import ReferralPage from './pages/Referral'
import type { Lang } from './i18n'

type Tab = 'shop' | 'profile' | 'referral'

export default function App() {
  const [tab, setTab]   = useState<Tab>('shop')
  const [me, setMe]     = useState<Me | null>(null)
  const [lang, setLang] = useState<Lang>('ru')
  const [botUser, setBotUser] = useState('lemur_shop_bot')

  useEffect(() => {
    window.Telegram?.WebApp?.expand()
    api.me().then(user => {
      setMe(user)
      setLang(user.lang as Lang)
    }).catch(() => {})
  }, [])

  return (
    <>
      <div style={{ flex: 1 }}>
        {tab === 'shop'     && <Shop     lang={lang} />}
        {tab === 'profile'  && <Profile  me={me} lang={lang} />}
        {tab === 'referral' && <ReferralPage lang={lang} botUsername={botUser} />}
      </div>
      <BottomNav active={tab} onChange={setTab} lang={lang} />
    </>
  )
}
