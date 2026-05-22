import { useState, useEffect, useRef } from 'react'
import { api, wheelApi, type WheelResult } from '../api'

const PALETTE = [
  '#FF6B2B', // 0 = player (orange, always)
  '#2AABEE',
  '#4CAF72',
  '#FFD700',
  '#E91E8C',
  '#9C27B0',
  '#FF5722',
  '#00BCD4',
  '#8BC34A',
  '#F44336',
]

const SPIN_MS   = 4800
const EXTRA_LAPS = 6
const BET_OPTS   = [10, 25, 50, 100, 250]

// Placeholder bets shown before first spin
const PREVIEW_BETS = [50, 40, 60, 35, 55, 45, 70, 30, 50, 65]

function easeOutQuart(t: number) {
  return 1 - Math.pow(1 - t, 4)
}

function drawWheel(
  ctx: CanvasRenderingContext2D,
  bets: number[],
  total: number,
  rotation: number,
  winnerIdx: number | null,
) {
  const W = ctx.canvas.width
  const H = ctx.canvas.height
  const cx = W / 2
  const cy = H / 2
  const R  = Math.min(cx, cy) - 12

  ctx.clearRect(0, 0, W, H)

  // ── sectors ─────────────────────────────────────────────────────────────
  let angle = rotation
  bets.forEach((b, i) => {
    const slice = (b / total) * 2 * Math.PI
    const end   = angle + slice
    const isWin = i === winnerIdx

    ctx.save()
    if (isWin) {
      ctx.shadowColor = PALETTE[i % PALETTE.length]
      ctx.shadowBlur  = 18
    }

    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, isWin ? R + 7 : R, angle, end)
    ctx.closePath()
    ctx.fillStyle = PALETTE[i % PALETTE.length]
    ctx.fill()
    ctx.strokeStyle = 'rgba(10,8,20,0.45)'
    ctx.lineWidth   = i === 0 ? 2 : 1.2
    ctx.stroke()
    ctx.restore()

    // label
    if (slice > 0.14) {
      const mid  = angle + slice / 2
      const lr   = R * 0.67
      const fs   = Math.min(12, Math.max(8, slice * 17))
      ctx.save()
      ctx.translate(cx + Math.cos(mid) * lr, cy + Math.sin(mid) * lr)
      ctx.rotate(mid + Math.PI / 2)
      ctx.fillStyle   = 'rgba(255,255,255,0.92)'
      ctx.font        = `bold ${fs}px system-ui`
      ctx.textAlign   = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(i === 0 ? `★${b}` : `${b}`, 0, 0)
      ctx.restore()
    }

    angle = end
  })

  // ── outer ring ───────────────────────────────────────────────────────────
  ctx.beginPath()
  ctx.arc(cx, cy, R, 0, Math.PI * 2)
  ctx.strokeStyle = 'rgba(255,255,255,0.1)'
  ctx.lineWidth   = 3
  ctx.stroke()

  // ── center hub ───────────────────────────────────────────────────────────
  ctx.beginPath()
  ctx.arc(cx, cy, 20, 0, Math.PI * 2)
  ctx.fillStyle = '#110820'
  ctx.fill()
  ctx.strokeStyle = 'rgba(255,107,43,0.5)'
  ctx.lineWidth   = 2
  ctx.stroke()

  ctx.fillStyle    = '#FF6B2B'
  ctx.font         = 'bold 8px system-ui'
  ctx.textAlign    = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('ВИ', cx, cy)
}

export default function Wheel() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rotRef    = useRef(0)
  const rafRef    = useRef(0)

  const [balance, setBalance] = useState<number | null>(null)
  const [bet,     setBet    ] = useState(50)
  const [status,  setStatus ] = useState<'idle' | 'loading' | 'spinning' | 'done'>('idle')
  const [result,  setResult ] = useState<WheelResult | null>(null)

  useEffect(() => {
    api.me().then(m => setBalance(m.balance_stars)).catch(() => {})
  }, [])

  // redraw preview when bet or idle state changes
  useEffect(() => {
    if (status !== 'idle' && status !== 'done') return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const bets  = result ? result.bets : [bet, ...PREVIEW_BETS.slice(1)]
    const total = bets.reduce((a, b) => a + b, 0)
    drawWheel(ctx, bets, total, rotRef.current, result?.winner_idx ?? null)
  })

  function spinTo(res: WheelResult) {
    const { bets, total_pool, winner_idx } = res
    const slices     = bets.map(b => (b / total_pool) * 2 * Math.PI)
    const winnerStart = slices.slice(0, winner_idx).reduce((a, b) => a + b, 0)
    const winnerMid  = winnerStart + slices[winner_idx] / 2

    // pointer is at top (-π/2); solve for rotation R:  R + winnerMid = -π/2
    const targetBase = -Math.PI / 2 - winnerMid
    const cur        = rotRef.current
    const k          = Math.ceil((cur + EXTRA_LAPS * 2 * Math.PI - targetBase) / (2 * Math.PI))
    const targetRot  = targetBase + k * 2 * Math.PI

    const startRot = cur
    const t0       = performance.now()
    const canvas   = canvasRef.current!
    const ctx      = canvas.getContext('2d')!

    cancelAnimationFrame(rafRef.current)
    function frame(now: number) {
      const t    = Math.min((now - t0) / SPIN_MS, 1)
      const ease = easeOutQuart(t)
      const rot  = startRot + (targetRot - startRot) * ease
      rotRef.current = rot
      drawWheel(ctx, bets, total_pool, rot, t >= 1 ? winner_idx : null)
      if (t < 1) rafRef.current = requestAnimationFrame(frame)
      else        setStatus('done')
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
      setStatus('spinning')
      spinTo(res)
    } catch (e: any) {
      setStatus('idle')
      alert(e.message || 'Помилка')
    }
  }

  const spinning = status === 'loading' || status === 'spinning'
  const noFunds  = balance !== null && balance < bet

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '16px 12px 20px', minHeight: '100%',
    }}>

      {/* header */}
      <div style={{
        width: '100%', display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: 6,
      }}>
        <div style={{ fontSize: 19, fontWeight: 800 }}>🎡 Колесо удачі</div>
        <div style={{
          fontSize: 14, fontWeight: 700,
          background: 'rgba(255,215,0,0.12)', border: '1px solid rgba(255,215,0,0.25)',
          borderRadius: 20, padding: '4px 10px',
        }}>
          ⭐ {balance ?? '…'}
        </div>
      </div>

      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 14, textAlign: 'center' }}>
        10 учасників · переможець забирає <strong style={{ color: 'var(--text)' }}>75% пулу</strong>
        <br />чим більша ставка — тим більший сектор
      </div>

      {/* wheel + pointer */}
      <div style={{ position: 'relative', marginBottom: 14 }}>
        {/* pointer arrow */}
        <div style={{
          position: 'absolute', top: 0, left: '50%',
          transform: 'translate(-50%, -6px)',
          width: 0, height: 0, zIndex: 2,
          borderLeft:  '11px solid transparent',
          borderRight: '11px solid transparent',
          borderTop:   '22px solid #FF6B2B',
          filter: 'drop-shadow(0 3px 6px rgba(255,107,43,0.7))',
        }} />
        <canvas
          ref={canvasRef}
          width={284}
          height={284}
          style={{ display: 'block', borderRadius: '50%' }}
        />
      </div>

      {/* pool preview */}
      {!spinning && result && (
        <div style={{
          fontSize: 12, color: 'var(--muted)', marginBottom: 10,
        }}>
          Пул: <strong style={{ color: 'var(--text)' }}>⭐{result.total_pool}</strong>
          &nbsp;·&nbsp;переможець отримав ⭐{result.payout}
        </div>
      )}

      {/* result card */}
      {status === 'done' && result && (
        <div style={{
          width: '100%', maxWidth: 300, borderRadius: 16, padding: '14px 18px',
          marginBottom: 14, textAlign: 'center',
          background: result.player_won
            ? 'linear-gradient(135deg,rgba(76,175,72,.18),rgba(76,175,72,.04))'
            : 'rgba(255,255,255,0.04)',
          border: `1px solid ${result.player_won ? 'rgba(76,175,72,.45)' : 'rgba(255,255,255,.1)'}`,
        }}>
          {result.player_won ? (
            <>
              <div style={{ fontSize: 34, marginBottom: 2 }}>🎉</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#4CAF72' }}>Ти виграв!</div>
              <div style={{ fontSize: 15, marginTop: 4 }}>
                +⭐{result.payout}
                <span style={{ fontSize: 12, color: 'var(--muted)', marginLeft: 6 }}>
                  (×{(result.payout / result.bets[0]).toFixed(1)})
                </span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
                Баланс: ⭐{result.new_balance}
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 34, marginBottom: 2 }}>😔</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--muted)' }}>Не пощастило</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
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
              padding: '6px 13px', borderRadius: 20, fontSize: 13, fontWeight: 700,
              background: bet === b ? 'var(--accent)' : 'rgba(255,255,255,0.07)',
              color: bet === b ? '#fff' : 'var(--muted)',
              border: 'none', cursor: 'pointer', transition: 'background .15s',
            }}>
              ⭐{b}
            </button>
          ))}
        </div>
      )}

      {/* spin button */}
      <button
        className="btn btn-primary"
        style={{ width: '100%', maxWidth: 284, fontSize: 16, fontWeight: 800, padding: '14px 0' }}
        onClick={spinning ? undefined : handleSpin}
        disabled={spinning || noFunds}
      >
        {status === 'loading'  ? '⏳ Завантаження...' :
         status === 'spinning' ? '🎡 Крутиться...'   :
         `🎡 Крутити  ⭐${bet}`}
      </button>

      {noFunds && !spinning && (
        <div style={{ fontSize: 12, color: '#FF5252', marginTop: 7 }}>
          Недостатньо зірок · поповни баланс
        </div>
      )}
    </div>
  )
}
