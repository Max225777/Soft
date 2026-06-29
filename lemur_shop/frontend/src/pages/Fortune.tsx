import { useState, useEffect, useRef } from 'react'
import { fortuneApi, type FortunePrize, type FortuneSpinResult, type FortuneRecentWin } from '../api'
import type { Me } from '../api'
import type { Lang } from '../i18n'

interface Props { me: Me | null; lang: Lang; onRefresh: () => void }

const SPIN_COST = 100

// ── Колесо: SVG-сегменти ────────────────────────────────────────────────────
function WheelSVG({ prizes, spinning, targetSeg, onDone }: {
  prizes: FortunePrize[]
  spinning: boolean
  targetSeg: number
  onDone: () => void
}) {
  const N = prizes.length || 8
  const R = 130
  const CX = 140, CY = 140
  const wheelRef = useRef<SVGGElement>(null)
  const angleRef = useRef(0)
  const animRef  = useRef<number | null>(null)
  const startRef = useRef<number | null>(null)

  useEffect(() => {
    if (!spinning || prizes.length === 0) return

    const segAngle = 360 / N
    // Кут центру цільового сегменту (0° = правий, але ми хочемо щоб покажчик зверху)
    // Сегмент 0 починається з -90°, тобто top = -90°
    const targetCenter = targetSeg * segAngle
    // Потрібно зупинитись так, щоб покажчик (зверху, -90°) вказував на targetSeg
    // Сегмент i покриває [i*segAngle, (i+1)*segAngle]
    // Колесо обертається, тому після rotation R, сегмент i виявляється на кутовій позиції: i*segAngle + R
    // Хочемо: targetCenter + rotation ≡ -90° (mod 360)  → rotation = -90 - targetCenter
    const finalAngle = (angleRef.current - (angleRef.current % 360)) + 360 * 6 + (270 - targetCenter)
    const duration   = 3200
    const startAngle = angleRef.current

    startRef.current = null
    const ease = (t: number) => 1 - Math.pow(1 - t, 4)

    const animate = (ts: number) => {
      if (startRef.current === null) startRef.current = ts
      const t = Math.min((ts - startRef.current) / duration, 1)
      const cur = startAngle + (finalAngle - startAngle) * ease(t)
      angleRef.current = cur
      if (wheelRef.current) {
        wheelRef.current.style.transform = `rotate(${cur}deg)`
        wheelRef.current.style.transformOrigin = `${CX}px ${CY}px`
      }
      if (t < 1) {
        animRef.current = requestAnimationFrame(animate)
      } else {
        angleRef.current = finalAngle
        onDone()
      }
    }
    animRef.current = requestAnimationFrame(animate)
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [spinning, targetSeg, prizes.length])

  if (prizes.length === 0) return null

  const segAngle = 360 / N
  const segments = prizes.map((p, i) => {
    const a1 = (i * segAngle - 90) * (Math.PI / 180)
    const a2 = ((i + 1) * segAngle - 90) * (Math.PI / 180)
    const x1 = CX + R * Math.cos(a1), y1 = CY + R * Math.sin(a1)
    const x2 = CX + R * Math.cos(a2), y2 = CY + R * Math.sin(a2)
    const large = segAngle > 180 ? 1 : 0
    const path = `M${CX},${CY} L${x1},${y1} A${R},${R} 0 ${large},1 ${x2},${y2} Z`
    const mid = (i + 0.5) * segAngle - 90
    const midRad = mid * (Math.PI / 180)
    const tx = CX + (R * 0.65) * Math.cos(midRad)
    const ty = CY + (R * 0.65) * Math.sin(midRad)
    return { path, tx, ty, angle: mid + 90, ...p }
  })

  return (
    <svg width={CX * 2} height={CY * 2} style={{ overflow: 'visible', display: 'block', margin: '0 auto' }}>
      {/* Glow filter */}
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
          <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="glow2">
          <feGaussianBlur stdDeviation="6" result="coloredBlur"/>
          <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      {/* Outer ring */}
      <circle cx={CX} cy={CY} r={R + 8} fill="none" stroke="rgba(255,107,43,.3)" strokeWidth={3} filter="url(#glow)" />
      <circle cx={CX} cy={CY} r={R + 12} fill="none" stroke="rgba(255,107,43,.12)" strokeWidth={2} />

      {/* Rotating wheel group */}
      <g ref={wheelRef}>
        {segments.map((seg, i) => (
          <g key={i}>
            <path d={seg.path} fill={seg.color} stroke="#0d0d12" strokeWidth={2} />
            <text
              x={seg.tx} y={seg.ty}
              textAnchor="middle" dominantBaseline="middle"
              transform={`rotate(${seg.angle}, ${seg.tx}, ${seg.ty})`}
              fontSize={seg.label.length > 6 ? 9 : 11} fontWeight={700} fill="#fff"
              style={{ userSelect: 'none', pointerEvents: 'none' }}
            >
              {seg.emoji} {seg.label.replace(/[⭐🌟💫💥🔥✨🎁🏆]/g, '').trim()}
            </text>
          </g>
        ))}
      </g>

      {/* Center hub */}
      <circle cx={CX} cy={CY} r={18} fill="#1a1a2e" stroke="rgba(255,107,43,.5)" strokeWidth={2.5} filter="url(#glow)" />
      <text x={CX} y={CY} textAnchor="middle" dominantBaseline="middle" fontSize={16}>🎡</text>

      {/* Top pointer */}
      <polygon
        points={`${CX - 10},${CY - R - 8} ${CX + 10},${CY - R - 8} ${CX},${CY - R + 10}`}
        fill="#ff6b2b" filter="url(#glow)"
      />
      <polygon
        points={`${CX - 10},${CY - R - 8} ${CX + 10},${CY - R - 8} ${CX},${CY - R + 10}`}
        fill="none" stroke="rgba(255,200,100,.6)" strokeWidth={1}
      />
    </svg>
  )
}

// ── Список останніх виграшів ─────────────────────────────────────────────────
function RecentWins({ wins }: { wins: FortuneRecentWin[] }) {
  if (wins.length === 0) return null
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: 'var(--muted)' }}>
        🏆 Останні виграші
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {wins.map((w, i) => {
          const ago = w.created_at
            ? (() => {
                const diff = Math.round((Date.now() - new Date(w.created_at).getTime()) / 1000)
                if (diff < 60) return `${diff}с тому`
                if (diff < 3600) return `${Math.floor(diff / 60)}хв тому`
                if (diff < 86400) return `${Math.floor(diff / 3600)}год тому`
                return `${Math.floor(diff / 86400)}д тому`
              })()
            : ''
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: 'var(--bg2)', borderRadius: 12, padding: '8px 12px',
              border: '1px solid var(--border)',
              animation: 'fadeIn .4s ease',
            }}>
              <div style={{ fontSize: 18 }}>
                {w.prize_type === 'account' ? '🎁' : '⭐'}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>
                  {w.user_display}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                  {w.prize_label}
                </div>
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{ago}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Екран після виграшу акаунту: вибір ───────────────────────────────────────
function ClaimChoice({
  result, lang, onDone
}: {
  result: FortuneSpinResult
  lang: Lang
  onDone: (claimType: 'stars' | 'account', res: any) => void
}) {
  const [loading, setLoading] = useState<'account' | 'stars' | null>(null)
  const [err, setErr] = useState<string | null>(null)

  async function claim(type: 'stars' | 'account') {
    setLoading(type); setErr(null)
    try {
      const res = await fortuneApi.claim(result.spin_id, type)
      onDone(type, res)
    } catch (e: any) {
      setErr(e.message ?? 'Помилка')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={{
      background: 'var(--bg2)', borderRadius: 20, padding: 20,
      border: '1px solid rgba(255,107,43,.3)',
      boxShadow: '0 0 40px rgba(255,107,43,.15)',
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 48, marginBottom: 8 }}>🎁</div>
      <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 4 }}>
        {result.prize_label}
      </div>
      <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 20 }}>
        Оберіть як отримати приз:
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button
          className="btn btn-primary"
          style={{ width: '100%', padding: '13px' }}
          disabled={!!loading}
          onClick={() => claim('account')}
        >
          {loading === 'account' ? '⏳...' : `📱 Отримати TG-акаунт ${result.prize_label}`}
        </button>
        <button
          className="btn btn-secondary"
          style={{ width: '100%', padding: '13px' }}
          disabled={!!loading}
          onClick={() => claim('stars')}
        >
          {loading === 'stars' ? '⏳...' : `⭐ Взяти ${result.prize_equiv} зірок замість акаунту`}
        </button>
      </div>
      {err && <div style={{ color: '#ff4444', fontSize: 12, marginTop: 10 }}>❌ {err}</div>}
      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 12 }}>
        При виборі акаунту — номер телефону прийде в Telegram
      </div>
    </div>
  )
}

// ── Головна сторінка Fortune ─────────────────────────────────────────────────
export default function Fortune({ me, lang, onRefresh }: Props) {
  const [prizes,  setPrizes]  = useState<FortunePrize[]>([])
  const [recent,  setRecent]  = useState<FortuneRecentWin[]>([])
  const [spinning, setSpinning] = useState(false)
  const [targetSeg, setTargetSeg] = useState(0)
  const [result,  setResult]  = useState<FortuneSpinResult | null>(null)
  const [phase,   setPhase]   = useState<'idle' | 'spinning' | 'result' | 'claim' | 'done'>('idle')
  const [claimRes, setClaimRes] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)

  const balance = me?.balance_stars ?? 0
  const canSpin = balance >= SPIN_COST && phase === 'idle'

  useEffect(() => {
    fortuneApi.prizes().then(setPrizes).catch(() => {})
    fortuneApi.recent().then(setRecent).catch(() => {})
  }, [])

  function refreshRecent() {
    fortuneApi.recent().then(setRecent).catch(() => {})
  }

  async function spin() {
    if (!canSpin) return
    setErr(null)
    setPhase('spinning')
    setSpinning(true)
    try {
      const res = await fortuneApi.spin()
      setResult(res)
      setTargetSeg(res.prize_seg)
      onRefresh()
    } catch (e: any) {
      setPhase('idle')
      setSpinning(false)
      setErr(e.message === 'insufficient_balance'
        ? 'Недостатньо зірок'
        : (e.message ?? 'Помилка'))
    }
  }

  function onWheelDone() {
    setSpinning(false)
    if (!result) return
    setTimeout(() => {
      if (result.needs_claim) {
        setPhase('claim')
      } else {
        setPhase('result')
        refreshRecent()
        onRefresh()
      }
    }, 400)
  }

  function handleClaimed(_type: string, res: any) {
    setClaimRes(res)
    setPhase('done')
    refreshRecent()
    onRefresh()
  }

  function reset() {
    setPhase('idle')
    setResult(null)
    setClaimRes(null)
    setTargetSeg(0)
  }

  // ── Результат (зірки) ───────────────────────────────────────────────────
  if (phase === 'result' && result) {
    return (
      <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minHeight: '60vh', gap: 16, paddingTop: 32 }}>
        <div style={{ fontSize: 72, animation: 'pop .4s ease' }}>{result.prize_emoji}</div>
        <div style={{ fontWeight: 800, fontSize: 26, color: result.prize_color, textShadow: `0 0 20px ${result.prize_color}` }}>
          {result.prize_label}
        </div>
        <div style={{ fontSize: 14, color: 'var(--muted)' }}>Нараховано на баланс!</div>
        <div style={{ fontWeight: 700, fontSize: 16 }}>Баланс: ⭐{result.new_balance}</div>
        <button className="btn btn-primary" style={{ marginTop: 12, padding: '12px 32px' }} onClick={reset}>
          🎡 Крутити ще
        </button>
      </div>
    )
  }

  // ── Результат (акаунт або зірки після claim) ────────────────────────────
  if (phase === 'done' && claimRes) {
    const isAcc = claimRes.claimed === 'account' && claimRes.phone && !claimRes.fallback
    return (
      <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minHeight: '60vh', gap: 14, paddingTop: 24 }}>
        <div style={{ fontSize: 64 }}>{isAcc ? '📱' : '⭐'}</div>
        <div style={{ fontWeight: 800, fontSize: 22 }}>
          {isAcc ? 'Акаунт отримано!' : `+${claimRes.stars} зірок`}
        </div>
        {isAcc ? (
          <div style={{
            background: 'rgba(42,171,238,.1)', border: '1px solid rgba(42,171,238,.3)',
            borderRadius: 16, padding: 16, width: '100%', maxWidth: 320,
          }}>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>📱 Номер телефону:</div>
            <div style={{ fontWeight: 800, fontSize: 20, color: '#2AABEE', letterSpacing: 1 }}>
              {claimRes.phone}
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8 }}>
              Замовлення #{claimRes.order_id} · Код прийде в боті
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 14, color: 'var(--muted)' }}>
            {claimRes.fallback ? 'Акаунт тимчасово недоступний — зараховано зірки' : 'Зараховано на баланс!'}
          </div>
        )}
        <div style={{ fontSize: 14 }}>Баланс: ⭐{claimRes.new_balance}</div>
        <button className="btn btn-primary" style={{ marginTop: 12, padding: '12px 32px' }} onClick={reset}>
          🎡 Крутити ще
        </button>
      </div>
    )
  }

  return (
    <div className="page">
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 8 }}>
        <div style={{ fontWeight: 900, fontSize: 24, background: 'linear-gradient(90deg, #ff6b2b, #ffd700, #ff6b2b)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          🎡 Колесо фортуни
        </div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
          Прокрутити — {SPIN_COST} ⭐ · Ваш баланс: ⭐{balance}
        </div>
      </div>

      {/* Wheel */}
      <div style={{
        position: 'relative', margin: '12px auto',
        background: 'radial-gradient(circle at 50% 50%, rgba(255,107,43,.05) 0%, transparent 70%)',
        padding: 10, borderRadius: '50%', width: 'fit-content',
      }}>
        <WheelSVG
          prizes={prizes}
          spinning={phase === 'spinning'}
          targetSeg={targetSeg}
          onDone={onWheelDone}
        />
      </div>

      {/* Claim choice (if account prize) */}
      {phase === 'claim' && result && (
        <div style={{ marginTop: 12 }}>
          <ClaimChoice result={result} lang={lang} onDone={handleClaimed} />
        </div>
      )}

      {/* Spin button */}
      {(phase === 'idle' || phase === 'spinning') && (
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          {err && <div style={{ color: '#ff4444', fontSize: 13, marginBottom: 8 }}>❌ {err}</div>}
          <button
            className="btn btn-primary"
            style={{
              width: '100%', padding: '15px', fontSize: 16, fontWeight: 800,
              background: canSpin
                ? 'linear-gradient(135deg, #ff6b2b, #e8530a)'
                : 'var(--card2)',
              boxShadow: canSpin ? '0 4px 24px rgba(255,107,43,.5)' : 'none',
              opacity: phase === 'spinning' ? 0.5 : 1,
              transition: 'all .2s',
            }}
            disabled={!canSpin || phase === 'spinning'}
            onClick={spin}
          >
            {phase === 'spinning' ? '⏳ Крутиться...' : `🎡 Крутити — ⭐${SPIN_COST}`}
          </button>
          {balance < SPIN_COST && phase === 'idle' && (
            <div style={{ fontSize: 12, color: '#ff4444', marginTop: 8 }}>
              Недостатньо зірок. Поповніть баланс!
            </div>
          )}
        </div>
      )}

      {/* Prize table */}
      {phase === 'idle' && prizes.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Можливі призи:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {prizes.map((p, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 5,
                background: `${p.color}18`, border: `1px solid ${p.color}44`,
                borderRadius: 10, padding: '5px 10px', fontSize: 11, fontWeight: 700,
                color: p.color,
              }}>
                {p.emoji} {p.label}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent wins */}
      <div style={{ marginTop: 24 }}>
        <RecentWins wins={recent} />
      </div>

      {/* CSS animations */}
      <style>{`
        @keyframes pop {
          0%   { transform: scale(0.5); opacity: 0; }
          60%  { transform: scale(1.2); }
          100% { transform: scale(1);   opacity: 1; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
