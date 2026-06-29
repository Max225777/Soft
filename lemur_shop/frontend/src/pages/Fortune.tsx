import { useState, useEffect, useRef } from 'react'
import { fortuneApi, type FortuneCat, type FortuneSpinResult, type FortuneRecentWin } from '../api'
import type { Me } from '../api'
import type { Lang } from '../i18n'

interface Props { me: Me | null; lang: Lang; onRefresh: () => void }

const SPIN_COST = 100

// ── Wheel SVG ────────────────────────────────────────────────────────────────
function WheelSVG({ cats, spinning, targetSeg, onDone }: {
  cats: FortuneCat[]
  spinning: boolean
  targetSeg: number
  onDone: () => void
}) {
  const N = cats.length || 6
  const R = 128
  const CX = 142, CY = 142
  const wheelRef = useRef<SVGGElement>(null)
  const angleRef = useRef(0)
  const animRef  = useRef<number | null>(null)
  const startRef = useRef<number | null>(null)

  useEffect(() => {
    if (!spinning || cats.length === 0) return
    const segAngle = 360 / N
    const finalAngle = (angleRef.current - (angleRef.current % 360)) + 360 * 7 + (270 - targetSeg * segAngle)
    const duration   = 3600
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
      if (t < 1) { animRef.current = requestAnimationFrame(animate) }
      else { angleRef.current = finalAngle; onDone() }
    }
    animRef.current = requestAnimationFrame(animate)
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [spinning, targetSeg, cats.length])

  if (cats.length === 0) return null
  const segAngle = 360 / N
  const segments = cats.map((c, i) => {
    const a1 = (i * segAngle - 90) * (Math.PI / 180)
    const a2 = ((i + 1) * segAngle - 90) * (Math.PI / 180)
    const x1 = CX + R * Math.cos(a1), y1 = CY + R * Math.sin(a1)
    const x2 = CX + R * Math.cos(a2), y2 = CY + R * Math.sin(a2)
    const large = segAngle > 180 ? 1 : 0
    const path = `M${CX},${CY} L${x1},${y1} A${R},${R} 0 ${large},1 ${x2},${y2} Z`
    const midRad = ((i + 0.5) * segAngle - 90) * (Math.PI / 180)
    const tx = CX + R * 0.62 * Math.cos(midRad)
    const ty = CY + R * 0.62 * Math.sin(midRad)
    const textAngle = (i + 0.5) * segAngle
    return { path, tx, ty, textAngle, ...c }
  })

  return (
    <svg width={CX * 2} height={CY * 2} style={{ overflow: 'visible', display: 'block', margin: '0 auto' }}>
      <defs>
        <filter id="fw-glow">
          <feGaussianBlur stdDeviation="4" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="fw-shadow">
          <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.4"/>
        </filter>
      </defs>

      {/* Outer glow rings */}
      <circle cx={CX} cy={CY} r={R + 14} fill="none" stroke="rgba(255,107,43,.15)" strokeWidth={4} />
      <circle cx={CX} cy={CY} r={R + 8}  fill="none" stroke="rgba(255,107,43,.35)" strokeWidth={2.5} filter="url(#fw-glow)" />

      {/* Rotating group */}
      <g ref={wheelRef}>
        {segments.map((seg, i) => (
          <g key={i}>
            <path d={seg.path} fill={seg.color} stroke="#0c0c12" strokeWidth={2.5} />
            {/* Lighter inner fill for alternating effect */}
            <path d={seg.path} fill="rgba(255,255,255,.06)" stroke="none" />
            <text
              x={seg.tx} y={seg.ty}
              textAnchor="middle" dominantBaseline="middle"
              transform={`rotate(${seg.textAngle}, ${seg.tx}, ${seg.ty})`}
              fontSize={11} fontWeight={800} fill="#fff"
              style={{ userSelect: 'none', pointerEvents: 'none', filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.8))' }}
            >
              {seg.emoji}
            </text>
            <text
              x={seg.tx} y={seg.ty + 13}
              textAnchor="middle" dominantBaseline="middle"
              transform={`rotate(${seg.textAngle}, ${seg.tx}, ${seg.ty + 13})`}
              fontSize={8} fontWeight={700} fill="rgba(255,255,255,.9)"
              style={{ userSelect: 'none', pointerEvents: 'none' }}
            >
              {seg.label.replace(/[\u{1F1E0}-\u{1F1FF}]{2}/gu, '').trim().slice(0, 8)}
            </text>
          </g>
        ))}
        {/* Segment dividers glow */}
        {segments.map((seg, i) => {
          const a = (i * segAngle - 90) * (Math.PI / 180)
          return (
            <line key={`d${i}`}
              x1={CX} y1={CY}
              x2={CX + R * Math.cos(a)} y2={CY + R * Math.sin(a)}
              stroke="rgba(255,255,255,.12)" strokeWidth={1}
            />
          )
        })}
      </g>

      {/* Center hub */}
      <circle cx={CX} cy={CY} r={22} fill="#0c0c12" stroke="rgba(255,107,43,.6)" strokeWidth={3} filter="url(#fw-glow)" />
      <text x={CX} y={CY} textAnchor="middle" dominantBaseline="middle" fontSize={18}>🎡</text>

      {/* Top pointer */}
      <polygon
        points={`${CX - 11},${CY - R - 6} ${CX + 11},${CY - R - 6} ${CX},${CY - R + 12}`}
        fill="#ff6b2b" filter="url(#fw-glow)"
      />
      <polygon
        points={`${CX - 11},${CY - R - 6} ${CX + 11},${CY - R - 6} ${CX},${CY - R + 12}`}
        fill="none" stroke="rgba(255,220,120,.5)" strokeWidth={1.5}
      />
    </svg>
  )
}

// ── Pool progress bar ─────────────────────────────────────────────────────────
function PoolBar({ poolBalance, cats }: { poolBalance: number; cats: FortuneCat[] }) {
  // Find nearest reachable prize
  const sorted = [...cats].sort((a, b) => a.threshold - b.threshold)
  const next = sorted.find(c => c.threshold > poolBalance) ?? sorted[sorted.length - 1]
  const pct = next ? Math.min(100, (poolBalance / next.threshold) * 100) : 100
  const ready = cats.filter(c => c.threshold <= poolBalance)

  return (
    <div style={{
      background: 'var(--bg2)', borderRadius: 16, padding: '14px 16px',
      border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)' }}>🏦 Призовий пул</div>
        <div style={{ fontSize: 15, fontWeight: 900, color: '#ffd700' }}>⭐{poolBalance}</div>
      </div>

      {/* Progress bar toward next prize */}
      <div style={{ marginBottom: 6 }}>
        <div style={{
          height: 8, background: 'var(--bg3, #1a1a2e)', borderRadius: 99,
          overflow: 'hidden', position: 'relative',
        }}>
          <div style={{
            height: '100%', width: `${pct}%`,
            background: `linear-gradient(90deg, #ff6b2b, ${next?.color ?? '#ffd700'})`,
            borderRadius: 99, transition: 'width .5s ease',
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10, color: 'var(--muted)' }}>
          <span>{poolBalance}⭐</span>
          <span>Наступний: {next?.label} ({next?.threshold}⭐)</span>
        </div>
      </div>

      {/* Ready prizes */}
      {ready.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
          {ready.map(c => (
            <span key={c.cat} style={{
              fontSize: 10, fontWeight: 700, padding: '2px 8px',
              background: `${c.color}22`, border: `1px solid ${c.color}55`,
              borderRadius: 99, color: c.color,
            }}>
              {c.emoji} {c.label} — ДОСТУПНО!
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Recent wins ───────────────────────────────────────────────────────────────
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
              border: '1px solid rgba(255,215,0,.15)',
              animation: 'fwFadeIn .4s ease',
            }}>
              <div style={{ fontSize: 18 }}>🎁</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>{w.user_display}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>{w.prize_label}</div>
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)', whiteSpace: 'nowrap' }}>{ago}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Win screen ────────────────────────────────────────────────────────────────
function WinScreen({ result, onReset }: { result: FortuneSpinResult; onReset: () => void }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      gap: 14, paddingTop: 20,
    }}>
      <div style={{ fontSize: 80, animation: 'fwPop .5s ease' }}>🎉</div>
      <div style={{
        fontWeight: 900, fontSize: 28,
        background: `linear-gradient(135deg, #ffd700, ${result.prize_color})`,
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        textAlign: 'center',
      }}>
        ВИГРАШ!
      </div>
      <div style={{
        fontSize: 18, fontWeight: 800, color: result.prize_color,
        textShadow: `0 0 20px ${result.prize_color}`,
        textAlign: 'center',
      }}>
        {result.prize_emoji} {result.prize_label}
      </div>

      {/* Phone number card */}
      <div style={{
        background: 'rgba(42,171,238,.1)', border: '1px solid rgba(42,171,238,.35)',
        borderRadius: 20, padding: '18px 22px', width: '100%', maxWidth: 320,
        textAlign: 'center', boxShadow: '0 0 30px rgba(42,171,238,.1)',
      }}>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>📱 Номер телефону:</div>
        <div style={{ fontWeight: 900, fontSize: 22, color: '#2AABEE', letterSpacing: 1.5 }}>
          {result.phone}
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 10 }}>
          Замовлення #{result.order_id} · Код входу прийде в боті
        </div>
      </div>

      <div style={{ fontSize: 13 }}>Баланс: ⭐{result.new_balance}</div>

      <button
        className="btn btn-primary"
        style={{ width: '100%', maxWidth: 320, padding: '14px', fontSize: 15, fontWeight: 800 }}
        onClick={onReset}
      >
        🎡 Крутити ще
      </button>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Fortune({ me, lang, onRefresh }: Props) {
  const [cats,     setCats]     = useState<FortuneCat[]>([])
  const [poolBal,  setPoolBal]  = useState(0)
  const [recent,   setRecent]   = useState<FortuneRecentWin[]>([])
  const [spinning, setSpinning] = useState(false)
  const [targetSeg, setTargetSeg] = useState(0)
  const [result,   setResult]   = useState<FortuneSpinResult | null>(null)
  const [phase,    setPhase]    = useState<'idle' | 'spinning' | 'done'>('idle')
  const [err,      setErr]      = useState<string | null>(null)

  const isAdmin = me?.is_admin ?? false
  const balance = me?.balance_stars ?? 0
  const canSpin = balance >= SPIN_COST && phase === 'idle'

  if (!isAdmin) {
    return (
      <div className="page" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 12 }}>
        <div style={{ fontSize: 48 }}>🔒</div>
        <div style={{ fontWeight: 800, fontSize: 18, textAlign: 'center' }}>Розділ недоступний</div>
        <div style={{ fontSize: 13, color: 'var(--muted)', textAlign: 'center' }}>Скоро відкриємо для всіх!</div>
      </div>
    )
  }

  useEffect(() => {
    fortuneApi.prizes().then(d => { setCats(d.cats); setPoolBal(d.pool_balance) }).catch(() => {})
    fortuneApi.recent().then(setRecent).catch(() => {})
  }, [])

  async function spin() {
    if (!canSpin) return
    setErr(null)
    setPhase('spinning')
    setSpinning(true)
    try {
      const res = await fortuneApi.spin()
      setResult(res)
      setTargetSeg(res.prize_seg)
      setPoolBal(res.pool_balance)
      onRefresh()
    } catch (e: any) {
      setPhase('idle')
      setSpinning(false)
      setErr(e.message === 'insufficient_balance' ? 'Недостатньо зірок' : (e.message ?? 'Помилка'))
    }
  }

  function onWheelDone() {
    setSpinning(false)
    setTimeout(() => {
      setPhase('done')
      if (result?.won) fortuneApi.recent().then(setRecent).catch(() => {})
    }, 500)
  }

  function reset() {
    setPhase('idle')
    setResult(null)
  }

  // Win result screen (full-page overlay style)
  if (phase === 'done' && result?.won) {
    return (
      <div className="page">
        <WinScreen result={result} onReset={reset} />
        <style>{`@keyframes fwPop{0%{transform:scale(.3);opacity:0}60%{transform:scale(1.2)}100%{transform:scale(1);opacity:1}}`}</style>
      </div>
    )
  }

  // No-win result (shown briefly inline before resetting)
  const showNoWin = phase === 'done' && result && !result.won

  return (
    <div className="page">
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 10 }}>
        <div style={{
          fontWeight: 900, fontSize: 22,
          background: 'linear-gradient(90deg, #ff6b2b, #ffd700, #ff6b2b)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          🎮 Міні-ігри — Колесо
        </div>
        <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
          Прокрут ⭐{SPIN_COST} · Ваш баланс: ⭐{balance}
        </div>
      </div>

      {/* Pool status */}
      <div style={{ marginBottom: 12 }}>
        <PoolBar poolBalance={poolBal} cats={cats} />
      </div>

      {/* Wheel */}
      <div style={{
        position: 'relative', margin: '0 auto 12px',
        width: 'fit-content',
        background: 'radial-gradient(circle at 50% 50%, rgba(255,107,43,.06) 0%, transparent 70%)',
        padding: 12, borderRadius: '50%',
      }}>
        <WheelSVG
          cats={cats}
          spinning={phase === 'spinning'}
          targetSeg={targetSeg}
          onDone={onWheelDone}
        />
      </div>

      {/* No-win notification */}
      {showNoWin && result && (
        <div style={{
          background: 'rgba(255,107,43,.08)', border: '1px solid rgba(255,107,43,.25)',
          borderRadius: 14, padding: '12px 16px', marginBottom: 12, textAlign: 'center',
          animation: 'fwFadeIn .4s ease',
        }}>
          <div style={{ fontSize: 15, fontWeight: 800, marginBottom: 4 }}>
            {result.prize_emoji} {result.prize_label}
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
            Пул поповнено! Потрібно ще ⭐{result.pool_threshold - result.pool_balance} для цього призу.
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#ffd700' }}>
            🏦 Пул: ⭐{result.pool_balance} / ⭐{result.pool_threshold}
          </div>
          <button
            className="btn btn-secondary"
            style={{ marginTop: 10, padding: '9px 24px', fontSize: 13 }}
            onClick={reset}
          >
            Крутити ще
          </button>
        </div>
      )}

      {/* Spin button */}
      {(phase === 'idle' || phase === 'spinning') && (
        <div style={{ marginBottom: 16 }}>
          {err && <div style={{ color: '#ff4444', fontSize: 13, marginBottom: 8, textAlign: 'center' }}>❌ {err}</div>}
          <button
            className="btn btn-primary"
            style={{
              width: '100%', padding: '15px', fontSize: 16, fontWeight: 800,
              background: canSpin
                ? 'linear-gradient(135deg, #ff6b2b, #e8530a)'
                : 'var(--card2)',
              boxShadow: canSpin ? '0 4px 24px rgba(255,107,43,.5)' : 'none',
              opacity: phase === 'spinning' ? 0.6 : 1,
            }}
            disabled={!canSpin || phase === 'spinning'}
            onClick={spin}
          >
            {phase === 'spinning' ? '⏳ Крутиться...' : `🎡 Крутити — ⭐${SPIN_COST}`}
          </button>
          {balance < SPIN_COST && phase === 'idle' && (
            <div style={{ fontSize: 12, color: '#ff4444', marginTop: 6, textAlign: 'center' }}>
              Недостатньо зірок. Поповніть баланс!
            </div>
          )}
        </div>
      )}

      {/* Prize list */}
      {phase === 'idle' && cats.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, fontWeight: 700 }}>
            МОЖЛИВІ ПРИЗИ
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[...cats].sort((a, b) => a.threshold - b.threshold).map(c => {
              const reachable = poolBal >= c.threshold
              return (
                <div key={c.cat} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  background: reachable ? `${c.color}18` : 'var(--bg2)',
                  border: `1px solid ${reachable ? c.color + '55' : 'var(--border)'}`,
                  borderRadius: 12, padding: '8px 12px',
                  transition: 'all .3s',
                }}>
                  <div style={{ fontSize: 20 }}>{c.emoji}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 800, color: reachable ? c.color : 'var(--text)' }}>
                      {c.label}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
                      Пул: {c.threshold}⭐
                    </div>
                  </div>
                  <div style={{
                    fontSize: 10, fontWeight: 700,
                    color: reachable ? c.color : 'var(--muted)',
                    background: reachable ? `${c.color}22` : 'var(--bg3, #1a1a2e)',
                    padding: '3px 8px', borderRadius: 99,
                  }}>
                    {reachable ? '✅ Доступно!' : `${Math.round((poolBal / c.threshold) * 100)}%`}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Recent wins */}
      <RecentWins wins={recent} />

      <style>{`
        @keyframes fwFadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes fwPop {
          0%   { transform: scale(.3); opacity: 0; }
          60%  { transform: scale(1.2); }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
