import { useState, useEffect, useRef } from 'react'
import { api, wheelApi, type WheelResult } from '../api'

// ── wheel visual config ────────────────────────────────────────────────────
const SECTORS = 12
const PALETTE = [
  '#FF6B2B','#2AABEE','#4CAF72','#FFD700',
  '#E91E8C','#9C27B0','#FF5722','#00BCD4',
  '#8BC34A','#F44336','#FF9800','#3F51B5',
]
const SPIN_MS    = 4600
const EXTRA_LAPS = 7
const BET_OPTS   = [10, 25, 50, 100, 250]

function easeOutQuart(t: number) {
  return 1 - Math.pow(1 - t, 4)
}

// win sector index (visually where the pointer lands on win)
const WIN_SECTOR = 0

function drawWheel(
  ctx: CanvasRenderingContext2D,
  rotation: number,
  highlight: boolean,
) {
  const W = ctx.canvas.width, H = ctx.canvas.height
  const cx = W / 2, cy = H / 2
  const R  = Math.min(cx, cy) - 12
  const slice = (2 * Math.PI) / SECTORS

  ctx.clearRect(0, 0, W, H)

  for (let i = 0; i < SECTORS; i++) {
    const start = rotation + i * slice
    const end   = start + slice
    const isWin = i === WIN_SECTOR && highlight

    ctx.save()
    if (isWin) {
      ctx.shadowColor = '#FFD700'
      ctx.shadowBlur  = 24
    }
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, isWin ? R + 8 : R, start, end)
    ctx.closePath()
    ctx.fillStyle = PALETTE[i % PALETTE.length]
    ctx.fill()
    ctx.strokeStyle = 'rgba(10,8,20,.4)'
    ctx.lineWidth   = 1.5
    ctx.stroke()
    ctx.restore()

    // label
    const mid = start + slice / 2
    const lr  = R * 0.70
    ctx.save()
    ctx.translate(cx + Math.cos(mid) * lr, cy + Math.sin(mid) * lr)
    ctx.rotate(mid + Math.PI / 2)
    ctx.fillStyle    = 'rgba(255,255,255,.88)'
    ctx.font         = 'bold 11px system-ui'
    ctx.textAlign    = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(i === WIN_SECTOR ? '🏆' : '✕', 0, 0)
    ctx.restore()
  }

  // outer ring
  ctx.beginPath()
  ctx.arc(cx, cy, R, 0, Math.PI * 2)
  ctx.strokeStyle = 'rgba(255,255,255,.1)'
  ctx.lineWidth   = 3
  ctx.stroke()

  // center hub
  ctx.beginPath()
  ctx.arc(cx, cy, 18, 0, Math.PI * 2)
  ctx.fillStyle = '#110820'
  ctx.fill()
  ctx.strokeStyle = 'rgba(255,107,43,.5)'
  ctx.lineWidth   = 2
  ctx.stroke()
}

export default function Wheel() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rotRef    = useRef(0)
  const rafRef    = useRef(0)

  const [balance,   setBalance  ] = useState<number | null>(null)
  const [pot,       setPot      ] = useState(0)
  const [bet,       setBet      ] = useState(50)
  const [status,    setStatus   ] = useState<'idle' | 'loading' | 'spinning' | 'done'>('idle')
  const [result,    setResult   ] = useState<WheelResult | null>(null)

  // initial draw
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    drawWheel(canvas.getContext('2d')!, rotRef.current, false)
  }, [])

  // load balance + pot
  useEffect(() => {
    api.me().then(m => setBalance(m.balance_stars)).catch(() => {})
    wheelApi.pot().then(p => setPot(p.pot_stars)).catch(() => {})
  }, [])

  // spin-to-sector animation
  function spinTo(won: boolean, onDone: () => void) {
    const canvas = canvasRef.current!
    const ctx    = canvas.getContext('2d')!
    const slice  = (2 * Math.PI) / SECTORS

    // target sector: WIN_SECTOR if won, random lose sector otherwise
    const targetSector = won
      ? WIN_SECTOR
      : 1 + Math.floor(Math.random() * (SECTORS - 1))

    // midpoint of target sector should land at pointer (-π/2 = top)
    const sectorMid = targetSector * slice + slice / 2
    const targetBase = -Math.PI / 2 - sectorMid
    const cur = rotRef.current
    const k   = Math.ceil((cur + EXTRA_LAPS * 2 * Math.PI - targetBase) / (2 * Math.PI))
    const targetRot = targetBase + k * 2 * Math.PI

    const startRot = cur
    const t0 = performance.now()

    cancelAnimationFrame(rafRef.current)
    function frame(now: number) {
      const t    = Math.min((now - t0) / SPIN_MS, 1)
      const ease = easeOutQuart(t)
      const rot  = startRot + (targetRot - startRot) * ease
      rotRef.current = rot
      drawWheel(ctx, rot, t >= 1 && won)
      if (t < 1) rafRef.current = requestAnimationFrame(frame)
      else        onDone()
    }
    rafRef.current = requestAnimationFrame(frame)
  }

  async function handleSpin() {
    if (status === 'loading' || status === 'spinning') return
    setStatus('loading')
    setResult(null)
    try {
      const res = await wheelApi.spin(bet)
      setResult(res)
      setBalance(res.new_balance)
      setPot(res.pot_stars)
      setStatus('spinning')
      spinTo(res.player_won, () => setStatus('done'))
    } catch (e: any) {
      setStatus('idle')
      alert(e.message || 'Помилка')
    }
  }

  const spinning = status === 'loading' || status === 'spinning'
  const noFunds  = balance !== null && balance < bet
  const potWin   = Math.round(pot * 0.7)

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '14px 12px 20px', minHeight: '100%',
    }}>

      {/* header */}
      <div style={{
        width: '100%', display: 'flex',
        justifyContent: 'space-between', alignItems: 'center', marginBottom: 10,
      }}>
        <div style={{ fontSize: 18, fontWeight: 800 }}>🎡 Колесо удачі</div>
        <div style={{
          fontSize: 13, fontWeight: 700,
          background: 'rgba(255,215,0,.1)', border: '1px solid rgba(255,215,0,.25)',
          borderRadius: 20, padding: '4px 10px',
        }}>
          ⭐ {balance ?? '…'}
        </div>
      </div>

      {/* jackpot banner */}
      <div style={{
        width: '100%', maxWidth: 300, borderRadius: 16, marginBottom: 14,
        padding: '14px 18px', textAlign: 'center',
        background: 'linear-gradient(135deg,rgba(255,107,43,.15),rgba(255,215,0,.08))',
        border: '1px solid rgba(255,215,0,.3)',
      }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 3, letterSpacing: 1, textTransform: 'uppercase' }}>
          Поточний банк
        </div>
        <div style={{
          fontSize: 32, fontWeight: 900, lineHeight: 1,
          background: 'linear-gradient(90deg,#FF6B2B,#FFD700)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          ⭐ {pot}
        </div>
        {pot > 0 && (
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
            переможець отримає ≈ <strong style={{ color: '#4CAF72' }}>⭐{potWin}</strong>
          </div>
        )}
        {pot === 0 && (
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
            банк порожній — перший хто крутить наповнює його
          </div>
        )}
      </div>

      {/* wheel + pointer */}
      <div style={{ position: 'relative', marginBottom: 12 }}>
        <div style={{
          position: 'absolute', top: 0, left: '50%',
          transform: 'translate(-50%, -8px)',
          width: 0, height: 0, zIndex: 2,
          borderLeft:  '12px solid transparent',
          borderRight: '12px solid transparent',
          borderTop:   '24px solid #FF6B2B',
          filter: 'drop-shadow(0 3px 8px rgba(255,107,43,.7))',
        }} />
        <canvas
          ref={canvasRef}
          width={280}
          height={280}
          style={{ display: 'block', borderRadius: '50%' }}
        />
      </div>

      {/* result card */}
      {status === 'done' && result && (
        <div style={{
          width: '100%', maxWidth: 300, borderRadius: 16, padding: '14px 18px',
          marginBottom: 12, textAlign: 'center',
          background: result.player_won
            ? 'linear-gradient(135deg,rgba(76,175,72,.2),rgba(76,175,72,.04))'
            : 'rgba(255,255,255,0.04)',
          border: `1px solid ${result.player_won ? 'rgba(76,175,72,.5)' : 'rgba(255,255,255,.1)'}`,
        }}>
          {result.player_won ? (
            <>
              <div style={{ fontSize: 36, marginBottom: 2 }}>🎉</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#4CAF72' }}>Ти виграв!</div>
              <div style={{ fontSize: 16, marginTop: 4 }}>+⭐{result.payout}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
                Баланс: ⭐{result.new_balance}
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 36, marginBottom: 2 }}>😔</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--muted)' }}>
                Не пощастило
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
                Банк поповнено · ⭐{result.pot_stars} у банку
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                Баланс: ⭐{result.new_balance}
              </div>
            </>
          )}
        </div>
      )}

      {/* bet selector */}
      {!spinning && (
        <div style={{ display: 'flex', gap: 7, marginBottom: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
          {BET_OPTS.map(b => (
            <button key={b} onClick={() => setBet(b)} style={{
              padding: '6px 14px', borderRadius: 20, fontSize: 13, fontWeight: 700,
              background: bet === b ? 'var(--accent)' : 'rgba(255,255,255,0.07)',
              color: bet === b ? '#fff' : 'var(--muted)',
              border: 'none', cursor: 'pointer',
            }}>
              ⭐{b}
            </button>
          ))}
        </div>
      )}

      {/* spin button */}
      <button
        className="btn btn-primary"
        style={{ width: '100%', maxWidth: 280, fontSize: 16, fontWeight: 800, padding: '14px 0' }}
        onClick={spinning ? undefined : handleSpin}
        disabled={spinning || noFunds}
      >
        {status === 'loading'  ? '⏳ Підключення...' :
         status === 'spinning' ? '🎡 Крутиться...'   :
         `🎡 Крутити  ⭐${bet}`}
      </button>

      {noFunds && !spinning && (
        <div style={{ fontSize: 12, color: '#FF5252', marginTop: 7 }}>
          Недостатньо зірок
        </div>
      )}

      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 12, textAlign: 'center', maxWidth: 280, lineHeight: 1.5 }}>
        Всі ставки йдуть у банк · переможець забирає 70% банку
      </div>
    </div>
  )
}
