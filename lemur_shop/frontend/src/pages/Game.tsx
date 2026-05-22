import { useState, useEffect, useRef, useCallback } from 'react'
import { gameApi } from '../api'

// ── Multiplier tiers (score → multiplier) ─────────────────────────────────────
const TIERS = [
  { score: 200,  mult: 1.5, label: '1.5×', color: '#4CAF72' },
  { score: 500,  mult: 2.0, label: '2×',   color: '#2AABEE' },
  { score: 1000, mult: 3.0, label: '3×',   color: '#FF6B2B' },
  { score: 2000, mult: 5.0, label: '5×',   color: '#FFD700' },
]

function currentMult(score: number) {
  for (let i = TIERS.length - 1; i >= 0; i--)
    if (score >= TIERS[i].score) return TIERS[i]
  return null
}

// ── Canvas helpers ────────────────────────────────────────────────────────────
const GRAVITY   = 0.42
const JUMP_VY   = -13
const SPRING_VY = -20
const P_W = 36, P_H = 36
const PLT_H = 12
const SPEED = 5
const MIN_GAP = 55, MAX_GAP = 120

interface Plt { id: number; x: number; y: number; w: number; spring: boolean; dx: number }

function drawPlayer(ctx: CanvasRenderingContext2D, x: number, y: number, face: number, sq: number) {
  ctx.save(); ctx.translate(x, y); ctx.scale(1 + sq * 0.2, 1 - sq * 0.15)
  ctx.fillStyle = 'rgba(0,0,0,.2)'; ctx.beginPath(); ctx.ellipse(0, 20, 15, 4, 0, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = '#FF6B2B'; ctx.beginPath(); ctx.ellipse(0, 0, 17, 21, 0, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = 'rgba(255,220,180,.45)'; ctx.beginPath(); ctx.ellipse(0, 5, 10, 12, 0, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = '#fff'
  ctx.beginPath(); ctx.ellipse(-7, -7, 7, 8, 0, 0, Math.PI * 2); ctx.ellipse(7, -7, 7, 8, 0, 0, Math.PI * 2); ctx.fill()
  const px = face * 2
  ctx.fillStyle = '#1a0a00'
  ctx.beginPath(); ctx.arc(-7 + px, -7, 4, 0, Math.PI * 2); ctx.arc(7 + px, -7, 4, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = '#fff'
  ctx.beginPath(); ctx.arc(-5 + px, -9, 1.5, 0, Math.PI * 2); ctx.arc(9 + px, -9, 1.5, 0, Math.PI * 2); ctx.fill()
  ctx.fillStyle = '#ff4466'; ctx.beginPath(); ctx.ellipse(0, 8, 9, 5, 0, 0, Math.PI); ctx.fill()
  ctx.fillStyle = '#cc2244'; ctx.beginPath(); ctx.ellipse(0, 8, 9, 3, 0, Math.PI, Math.PI * 2); ctx.fill()
  ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.beginPath(); ctx.arc(-3, 2, 1.5, 0, Math.PI * 2); ctx.arc(3, 2, 1.5, 0, Math.PI * 2); ctx.fill()
  ctx.restore()
}

function drawPlt(ctx: CanvasRenderingContext2D, p: Plt) {
  ctx.shadowColor = p.spring ? '#FF6B2B' : '#26A96C'; ctx.shadowBlur = 7
  ctx.fillStyle   = p.spring ? '#FF6B2B' : '#26A96C'
  ctx.beginPath(); ctx.roundRect(p.x, p.y, p.w, PLT_H, 6); ctx.fill()
  ctx.fillStyle = 'rgba(255,255,255,.22)'; ctx.beginPath(); ctx.roundRect(p.x + 4, p.y + 2, p.w - 8, 4, 2); ctx.fill()
  ctx.shadowBlur = 0
}

let _pid = 0
function mkPlt(y: number, W: number): Plt {
  const w = 55 + Math.random() * 35
  return { id: _pid++, x: Math.random() * (W - w), y, w, spring: Math.random() < 0.1, dx: Math.random() < 0.15 ? (Math.random() < 0.5 ? 1.2 : -1.2) : 0 }
}
function initPlts(W: number, H: number): Plt[] {
  const out: Plt[] = [{ id: _pid++, x: W / 2 - 40, y: H - 80, w: 80, spring: false, dx: 0 }]
  let y = H - 80
  for (let i = 0; i < 14; i++) { y -= MIN_GAP + Math.random() * (MAX_GAP - MIN_GAP); out.push(mkPlt(y, W)) }
  return out
}

// ── Multiplier strip (drawn on canvas) ────────────────────────────────────────
function drawStrip(ctx: CanvasRenderingContext2D, W: number, score: number) {
  const h = 44, pad = 6, gap = 5
  const itemW = (W - pad * 2 - gap * (TIERS.length - 1)) / TIERS.length
  // background
  ctx.fillStyle = 'rgba(0,0,0,.55)'
  ctx.fillRect(0, 0, W, h)

  TIERS.forEach((t, i) => {
    const x = pad + i * (itemW + gap)
    const active = score >= t.score
    // pill bg
    ctx.fillStyle = active ? t.color : 'rgba(255,255,255,.08)'
    ctx.beginPath(); ctx.roundRect(x, 6, itemW, h - 12, 8); ctx.fill()
    // glow when active
    if (active) { ctx.shadowColor = t.color; ctx.shadowBlur = 10 }
    // text
    ctx.fillStyle = active ? '#fff' : 'rgba(255,255,255,.35)'
    ctx.font = `bold ${Math.floor(itemW / 3.5)}px system-ui`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(t.label, x + itemW / 2, h / 2)
    ctx.shadowBlur = 0
  })
}

// ── Types ─────────────────────────────────────────────────────────────────────
type GS = 'idle' | 'loading' | 'playing' | 'submitting' | 'done'
interface Status { can_play_free: boolean; min_bet: number; balance_stars: number }
interface Result { score: number; bet: number; multiplier: number; stars_won: number; net: number; new_balance: number }

// ── Component ─────────────────────────────────────────────────────────────────
export default function Game() {
  const [gs, setGs]       = useState<GS>('idle')
  const [status, setStatus] = useState<Status | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [bet, setBet]     = useState(10)
  const [score, setScore] = useState(0)
  const [err, setErr]     = useState<string | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const tokenRef  = useRef('')
  const betRef    = useRef(10)
  const scoreRef  = useRef(0)
  const rafRef    = useRef(0)

  const loadStatus = useCallback(() => {
    gameApi.status().then(d => { setStatus(d); if (bet < d.min_bet) setBet(d.min_bet) }).catch(() => {})
  }, [bet])
  useEffect(() => { loadStatus() }, [loadStatus])

  // ── Start ──────────────────────────────────────────────────────────────────
  async function startGame() {
    setErr(null); setGs('loading'); setScore(0); scoreRef.current = 0
    try {
      const r = await gameApi.start(bet)
      tokenRef.current = r.token; betRef.current = r.bet
      setGs('playing')
    } catch (e: any) { setErr(e.message ?? 'Error'); setGs('idle') }
  }

  // ── Submit ─────────────────────────────────────────────────────────────────
  const submit = useCallback(async (finalScore: number) => {
    setGs('submitting')
    try {
      const res = await gameApi.finish(tokenRef.current, finalScore)
      setResult(res); setGs('done'); loadStatus()
    } catch { setGs('done') }
  }, [loadStatus])

  // ── Game loop ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (gs !== 'playing') return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const W = canvas.width, H = canvas.height
    const STRIP_H = 44

    let px = W / 2, py = H - 120, pvx = 0, pvy = -10
    let face = 0, squish = 0, camY = 0, maxCamY = 0
    let plts = initPlts(W, H)
    let running = true
    const keys = new Set<string>()
    let touchX = -1

    const onK = (e: KeyboardEvent) => { e.type === 'keydown' ? keys.add(e.key) : keys.delete(e.key) }
    const onTS = (e: TouchEvent) => { touchX = e.touches[0].clientX }
    const onTM = (e: TouchEvent) => { touchX = e.touches[0].clientX; e.preventDefault() }
    const onTE = () => { touchX = -1 }

    window.addEventListener('keydown', onK); window.addEventListener('keyup', onK)
    canvas.addEventListener('touchstart', onTS, { passive: false })
    canvas.addEventListener('touchmove',  onTM, { passive: false })
    canvas.addEventListener('touchend',   onTE)

    function loop() {
      if (!running) return
      // input
      let dir = 0
      if (touchX >= 0) dir = touchX < W / 2 ? -1 : 1
      else if (keys.has('ArrowLeft')  || keys.has('a')) dir = -1
      else if (keys.has('ArrowRight') || keys.has('d')) dir = 1
      face = dir

      // physics
      pvx = dir * SPEED; pvy += GRAVITY; px += pvx; py += pvy
      if (px < -P_W / 2) px = W + P_W / 2
      if (px > W + P_W / 2) px = -P_W / 2
      if (squish > 0) squish = Math.max(0, squish - 0.1)

      // platform collision
      if (pvy > 0) {
        for (const p of plts) {
          const sy = p.y - camY
          if (py - pvy + P_H / 2 <= sy + PLT_H && py + P_H / 2 >= sy &&
              px + P_W / 2 > p.x && px - P_W / 2 < p.x + p.w) {
            pvy = p.spring ? SPRING_VY : JUMP_VY; squish = 1; py = sy - P_H / 2; break
          }
        }
      }

      // camera
      const thr = H * 0.42
      if (py < thr) { const d = thr - py; camY += d; py = thr }
      if (camY > maxCamY) {
        maxCamY = camY
        const s = Math.round(maxCamY / 3.5)
        scoreRef.current = s; setScore(s)
      }

      // platform updates & generation
      for (const p of plts) { if (p.dx) { p.x += p.dx; if (p.x < 0 || p.x + p.w > W) p.dx *= -1 } }
      let arr = plts.filter(p => p.y - camY < H + 60)
      const topY = arr.length ? Math.min(...arr.map(p => p.y)) : camY
      let gy = topY
      while (gy > camY - 20) { gy -= MIN_GAP + Math.random() * 30; arr.push(mkPlt(gy, W)) }
      plts = arr

      // game over
      if (py - camY > H + 60) {
        running = false; cancelAnimationFrame(rafRef.current)
        window.removeEventListener('keydown', onK); window.removeEventListener('keyup', onK)
        canvas.removeEventListener('touchstart', onTS); canvas.removeEventListener('touchmove', onTM); canvas.removeEventListener('touchend', onTE)
        submit(scoreRef.current); return
      }

      // ── Draw ───────────────────────────────────────────────────────────────
      // bg
      const bg = ctx.createLinearGradient(0, 0, 0, H)
      const t = Math.min(1, scoreRef.current / 2000)
      bg.addColorStop(0, `rgb(${Math.round(10+t*5)},${Math.round(8+t*2)},${Math.round(22+t*18)})`)
      bg.addColorStop(1, `rgb(15,12,28)`)
      ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H)

      // stars bg
      ctx.fillStyle = 'rgba(255,255,255,.35)'
      for (let i = 0; i < 20; i++) {
        const seed = Math.floor(camY / 80)
        ctx.beginPath(); ctx.arc(((seed * 73 + i * 137) % W + W) % W, ((seed * 51 + i * 97) % (H - STRIP_H) + STRIP_H + W) % (H - STRIP_H) + STRIP_H, .6 + (i % 3) * .5, 0, Math.PI * 2); ctx.fill()
      }

      // platforms
      for (const p of plts) {
        const sy = p.y - camY + STRIP_H
        if (sy > STRIP_H - 20 && sy < H + 20) drawPlt(ctx, { ...p, y: sy })
      }

      // player (offset by strip)
      drawPlayer(ctx, px, py + STRIP_H, face, squish)

      // score bottom badge
      ctx.fillStyle = 'rgba(0,0,0,.45)'; ctx.beginPath(); ctx.roundRect(W / 2 - 50, H - 38, 100, 28, 10); ctx.fill()
      ctx.fillStyle = '#FFB830'; ctx.font = 'bold 14px system-ui'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText(`${scoreRef.current} м`, W / 2, H - 24)

      // multiplier strip ON TOP
      drawStrip(ctx, W, scoreRef.current)

      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => {
      running = false; cancelAnimationFrame(rafRef.current)
      window.removeEventListener('keydown', onK); window.removeEventListener('keyup', onK)
      canvas.removeEventListener('touchstart', onTS); canvas.removeEventListener('touchmove', onTM); canvas.removeEventListener('touchend', onTE)
    }
  }, [gs, submit])

  const canvasH = typeof window !== 'undefined' ? window.innerHeight - 60 : 600
  const canvasW = typeof window !== 'undefined' ? Math.min(window.innerWidth, 430) : 390

  if (gs === 'playing') {
    return (
      <canvas ref={canvasRef} width={canvasW} height={canvasH}
        style={{ display: 'block', width: canvasW, height: canvasH, touchAction: 'none', userSelect: 'none' }} />
    )
  }

  const isFree = status?.can_play_free ?? true
  const bal    = status?.balance_stars ?? 0

  const BETS = [10, 25, 50, 100].filter(b => b <= Math.max(10, bal))

  return (
    <div className="page" style={{ paddingBottom: 80 }}>
      {/* Hero */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428, #141018)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20, padding: '20px 16px', marginBottom: 12, textAlign: 'center',
      }}>
        <div style={{ fontSize: 48, marginBottom: 4 }}>🦎</div>
        <div style={{ fontWeight: 800, fontSize: 22 }}>Лемур Джамп</div>
        <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 2 }}>Стрибай вище — множ ставку!</div>
        <div style={{ fontWeight: 700, fontSize: 22, color: 'var(--orange)', marginTop: 10 }}>⭐ {bal}</div>
      </div>

      {/* Multiplier strip preview */}
      <div style={{
        background: 'rgba(0,0,0,.4)', border: '1px solid var(--border)',
        borderRadius: 14, padding: '12px 10px', marginBottom: 12,
        display: 'flex', gap: 6,
      }}>
        {TIERS.map(t => (
          <div key={t.mult} style={{
            flex: 1, textAlign: 'center', padding: '8px 4px', borderRadius: 10,
            background: `${t.color}22`, border: `1px solid ${t.color}55`,
          }}>
            <div style={{ fontWeight: 800, fontSize: 16, color: t.color }}>{t.label}</div>
            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{t.score}м</div>
          </div>
        ))}
      </div>

      {/* Result */}
      {gs === 'done' && result && (
        <div style={{
          background: result.net >= 0 ? 'rgba(76,175,114,.12)' : 'rgba(255,60,60,.08)',
          border: `1px solid ${result.net >= 0 ? 'rgba(76,175,114,.4)' : 'rgba(255,60,60,.3)'}`,
          borderRadius: 16, padding: '16px', marginBottom: 12, textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 6 }}>
            {result.multiplier === 0 ? '💀' : result.multiplier >= 5 ? '🏆' : result.multiplier >= 3 ? '🔥' : result.multiplier >= 2 ? '😎' : '🙂'}
          </div>
          <div style={{ fontWeight: 800, fontSize: 16 }}>{result.score} м</div>
          {result.multiplier > 0 ? (
            <>
              <div style={{ fontWeight: 800, fontSize: 28, color: 'var(--orange)', margin: '6px 0' }}>
                {result.multiplier}× → ⭐{result.stars_won}
              </div>
              <div style={{ fontSize: 13, color: result.net >= 0 ? '#4CAF72' : '#ff5555' }}>
                {result.net >= 0 ? `+${result.net} ⭐ прибуток` : `${result.net} ⭐ збиток`}
              </div>
            </>
          ) : (
            <div style={{ fontWeight: 700, fontSize: 18, color: '#ff5555', margin: '6px 0' }}>
              ⭐{result.bet} втрачено
            </div>
          )}
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 6 }}>Баланс: ⭐{result.new_balance}</div>
        </div>
      )}

      {err && (
        <div style={{ background: 'rgba(255,60,60,.1)', border: '1px solid rgba(255,60,60,.3)', borderRadius: 10, padding: '10px 14px', marginBottom: 12, fontSize: 13, color: '#ff5555' }}>
          {err === 'insufficient_balance' ? '❌ Недостатньо зірок' : `❌ ${err}`}
        </div>
      )}

      {/* Bet selector (only if not free) */}
      {!isFree && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>Ставка ⭐</div>
          <div style={{ display: 'flex', gap: 8 }}>
            {BETS.map(b => (
              <button key={b} onClick={() => setBet(b)} style={{
                flex: 1, padding: '10px 4px', borderRadius: 10, cursor: 'pointer',
                fontWeight: 800, fontSize: 15,
                background: bet === b ? 'rgba(255,107,43,.2)' : 'var(--bg2)',
                color: bet === b ? 'var(--orange)' : 'var(--text)',
                border: `1px solid ${bet === b ? 'rgba(255,107,43,.5)' : 'var(--border)'}`,
              }}>⭐{b}</button>
            ))}
          </div>
        </div>
      )}

      <button className="btn btn-primary" style={{ fontSize: 16, padding: '14px', marginBottom: 10 }}
        disabled={gs === 'loading' || gs === 'submitting' || bal < (isFree ? 0 : bet)}
        onClick={startGame}>
        {gs === 'loading' || gs === 'submitting' ? '⏳...'
          : isFree ? '🎮 Безкоштовна гра!'
          : `🎮 Грати (ставка ⭐${bet})`}
      </button>

      {isFree && (
        <div style={{ background: 'rgba(76,175,114,.1)', border: '1px solid rgba(76,175,114,.25)', borderRadius: 10, padding: '8px 12px', marginBottom: 12, fontSize: 13, color: '#4CAF72', textAlign: 'center' }}>
          🎁 Сьогоднішня безкоштовна спроба — ставка ⭐10
        </div>
      )}

      {/* Tiers table */}
      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>Таблиця множників</div>
        {TIERS.map(t => (
          <div key={t.mult} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 13, color: 'var(--muted)' }}>від {t.score} м</div>
            <div style={{ fontWeight: 800, fontSize: 15, color: t.color }}>{t.label}</div>
          </div>
        ))}
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8, textAlign: 'center' }}>
          Якщо нижче 200м — ставка втрачається
        </div>
      </div>

      <div className="card" style={{ marginTop: 10, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
        📱 Торкніться лівої/правої половини для руху · ⌨️ ←→
      </div>
    </div>
  )
}
