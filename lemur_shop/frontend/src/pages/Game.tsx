import { useState, useEffect, useRef, useCallback } from 'react'
import { gameApi } from '../api'

// ── Constants ─────────────────────────────────────────────────────────────────
const GRAVITY    = 0.42
const JUMP_VY    = -13
const SPRING_VY  = -20
const P_W        = 36
const P_H        = 36
const PLT_H      = 12
const SPEED      = 5
const MIN_GAP    = 55
const MAX_GAP    = 120

const STARS_FOR_SCORE = (s: number) =>
  s < 300 ? 2 : s < 700 ? 5 : s < 1200 ? 12 : s < 2000 ? 25 : s < 3000 ? 45 : 75

interface Plt { id: number; x: number; y: number; w: number; spring: boolean; dx: number }

// ── Draw helpers ──────────────────────────────────────────────────────────────
function drawPlayer(ctx: CanvasRenderingContext2D, x: number, y: number, face: number, squish: number) {
  const sx = 1 + squish * 0.25
  const sy = 1 - squish * 0.2
  ctx.save()
  ctx.translate(x, y)
  ctx.scale(sx, sy)

  // shadow
  ctx.fillStyle = 'rgba(0,0,0,0.25)'
  ctx.beginPath()
  ctx.ellipse(0, 20, 16, 5, 0, 0, Math.PI * 2)
  ctx.fill()

  // body
  ctx.fillStyle = '#FF6B2B'
  ctx.beginPath()
  ctx.ellipse(0, 0, 17, 21, 0, 0, Math.PI * 2)
  ctx.fill()

  // belly
  ctx.fillStyle = 'rgba(255,220,180,0.5)'
  ctx.beginPath()
  ctx.ellipse(0, 5, 10, 12, 0, 0, Math.PI * 2)
  ctx.fill()

  // eyes white
  ctx.fillStyle = '#fff'
  ctx.beginPath()
  ctx.ellipse(-7, -7, 7, 8, 0, 0, Math.PI * 2)
  ctx.ellipse(7, -7, 7, 8, 0, 0, Math.PI * 2)
  ctx.fill()

  // pupils
  const px = face * 2
  ctx.fillStyle = '#1a0a00'
  ctx.beginPath()
  ctx.arc(-7 + px, -7, 4, 0, Math.PI * 2)
  ctx.arc(7 + px, -7, 4, 0, Math.PI * 2)
  ctx.fill()

  // eye shine
  ctx.fillStyle = '#fff'
  ctx.beginPath()
  ctx.arc(-5 + px, -9, 1.5, 0, Math.PI * 2)
  ctx.arc(9 + px, -9, 1.5, 0, Math.PI * 2)
  ctx.fill()

  // lips (big, expressive)
  ctx.fillStyle = '#ff4466'
  ctx.beginPath()
  ctx.ellipse(0, 8, 9, 5, 0, 0, Math.PI)
  ctx.fill()
  ctx.fillStyle = '#cc2244'
  ctx.beginPath()
  ctx.ellipse(0, 8, 9, 3, 0, Math.PI, Math.PI * 2)
  ctx.fill()

  // nostrils
  ctx.fillStyle = 'rgba(0,0,0,0.3)'
  ctx.beginPath()
  ctx.arc(-3, 2, 1.5, 0, Math.PI * 2)
  ctx.arc(3, 2, 1.5, 0, Math.PI * 2)
  ctx.fill()

  ctx.restore()
}

function drawPlatform(ctx: CanvasRenderingContext2D, p: Plt) {
  const r = PLT_H / 2
  if (p.spring) {
    ctx.shadowColor = '#FF6B2B'
    ctx.shadowBlur = 8
    ctx.fillStyle = '#FF6B2B'
  } else {
    ctx.shadowColor = '#26A96C'
    ctx.shadowBlur = 6
    ctx.fillStyle = '#26A96C'
  }
  ctx.beginPath()
  ctx.roundRect(p.x, p.y, p.w, PLT_H, r)
  ctx.fill()
  // shine
  ctx.fillStyle = 'rgba(255,255,255,0.25)'
  ctx.beginPath()
  ctx.roundRect(p.x + 4, p.y + 2, p.w - 8, 4, 2)
  ctx.fill()
  ctx.shadowBlur = 0
}

// ── Generate platforms ────────────────────────────────────────────────────────
let _pid = 0
function makePlt(y: number, canvasW: number, score: number): Plt {
  const w = 55 + Math.random() * 35
  const x = Math.random() * (canvasW - w)
  const spring = Math.random() < 0.1 + score / 20000
  const moving = !spring && Math.random() < 0.15
  return { id: _pid++, x, y, w, spring, dx: moving ? (Math.random() < 0.5 ? 1.2 : -1.2) : 0 }
}

function initPlatforms(cW: number, cH: number): Plt[] {
  const plts: Plt[] = []
  // Starting platform under player
  plts.push({ id: _pid++, x: cW / 2 - 40, y: cH - 80, w: 80, spring: false, dx: 0 })
  let y = cH - 80
  for (let i = 0; i < 14; i++) {
    y -= MIN_GAP + Math.random() * (MAX_GAP - MIN_GAP)
    plts.push(makePlt(y, cW, 0))
  }
  return plts
}

// ── Main component ────────────────────────────────────────────────────────────
type GameState = 'idle' | 'loading' | 'playing' | 'dead' | 'submitting' | 'done'

interface Status { can_play_free: boolean; cost_stars: number; balance_stars: number }
interface Result { stars_earned: number; score: number; new_balance: number }

export default function Game() {
  const [gstate, setGstate]   = useState<GameState>('idle')
  const [status, setStatus]   = useState<Status | null>(null)
  const [result, setResult]   = useState<Result | null>(null)
  const [score,  setScore]    = useState(0)
  const [err,    setErr]      = useState<string | null>(null)
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const tokenRef   = useRef<string>('')
  const stateRef   = useRef<GameState>('idle')
  const rafRef     = useRef<number>(0)
  const scoreRef   = useRef(0)

  stateRef.current = gstate

  const loadStatus = useCallback(() => {
    gameApi.status().then(setStatus).catch(() => {})
  }, [])

  useEffect(() => { loadStatus() }, [loadStatus])

  // ── Start game ──────────────────────────────────────────────────────────────
  async function startGame() {
    setErr(null)
    setGstate('loading')
    try {
      const { token } = await gameApi.start()
      tokenRef.current = token
      setScore(0)
      scoreRef.current = 0
      setGstate('playing')
    } catch (e: any) {
      setErr(e.message ?? 'Error')
      setGstate('idle')
    }
  }

  // ── Submit result ───────────────────────────────────────────────────────────
  const submitResult = useCallback(async (finalScore: number) => {
    setGstate('submitting')
    try {
      const res = await gameApi.finish(tokenRef.current, finalScore)
      setResult(res)
      setGstate('done')
      loadStatus()
    } catch {
      setGstate('done')
    }
  }, [loadStatus])

  // ── Game loop ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (gstate !== 'playing') return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!

    const W = canvas.width
    const H = canvas.height

    // Player state
    let px    = W / 2
    let py    = H - 120
    let pvx   = 0
    let pvy   = -10
    let face  = 0
    let squish = 0

    // Camera
    let camY    = 0
    let maxCamY = 0
    let gameScore = 0

    // Platforms
    let plts = initPlatforms(W, H)

    // Input
    let inputDir = 0
    const keys = new Set<string>()

    function onKey(e: KeyboardEvent) {
      if (e.type === 'keydown') keys.add(e.key)
      else keys.delete(e.key)
    }

    // Touch
    let touchX = -1
    function onTouchStart(e: TouchEvent) { touchX = e.touches[0].clientX }
    function onTouchMove(e: TouchEvent)  { touchX = e.touches[0].clientX; e.preventDefault() }
    function onTouchEnd()                { touchX = -1 }

    window.addEventListener('keydown', onKey)
    window.addEventListener('keyup',   onKey)
    canvas.addEventListener('touchstart', onTouchStart, { passive: false })
    canvas.addEventListener('touchmove',  onTouchMove,  { passive: false })
    canvas.addEventListener('touchend',   onTouchEnd)

    let running = true

    function loop() {
      if (!running) return

      // Input
      if (touchX >= 0) inputDir = touchX < W / 2 ? -1 : 1
      else if (keys.has('ArrowLeft') || keys.has('a'))  inputDir = -1
      else if (keys.has('ArrowRight') || keys.has('d')) inputDir = 1
      else inputDir = 0

      face = inputDir

      // Physics
      pvx = inputDir * SPEED
      pvy += GRAVITY
      px += pvx
      py += pvy

      // Wrap
      if (px < -P_W / 2)   px = W + P_W / 2
      if (px > W + P_W / 2) px = -P_W / 2

      // Squish
      if (squish > 0) squish = Math.max(0, squish - 0.1)

      // Platform collision (only when falling)
      if (pvy > 0) {
        for (const p of plts) {
          const screenPY = p.y - camY
          const botY = py + P_H / 2
          const prevBotY = botY - pvy

          if (prevBotY <= screenPY + PLT_H &&
              botY >= screenPY &&
              px + P_W / 2 > p.x &&
              px - P_W / 2 < p.x + p.w) {
            pvy = p.spring ? SPRING_VY : JUMP_VY
            squish = 1
            py = screenPY - P_H / 2
            break
          }
        }
      }

      // Camera follows player up
      const threshold = H * 0.4
      if (py < threshold) {
        const delta = threshold - py
        camY += delta
        py = threshold
        if (camY > maxCamY) {
          maxCamY = camY
          gameScore = Math.round(maxCamY / 3.5)
          scoreRef.current = gameScore
          setScore(gameScore)
        }
      }

      // Move platforms & generate new ones
      for (const p of plts) {
        if (p.dx !== 0) {
          p.x += p.dx
          if (p.x < 0 || p.x + p.w > W) p.dx *= -1
        }
      }

      // Remove platforms far below camera
      const before = plts.filter(p => p.y - camY < H + 60)

      // Generate new platforms above
      const topY = Math.min(...before.map(p => p.y))
      let genY = topY
      const gap = Math.max(MIN_GAP, MAX_GAP - gameScore / 30)
      while (genY > camY - 20) {
        genY -= gap + Math.random() * 30
        before.push(makePlt(genY, W, gameScore))
      }
      plts = before

      // Game over check
      if (py - camY > H + 60) {
        running = false
        const finalScore = scoreRef.current
        cancelAnimationFrame(rafRef.current)
        window.removeEventListener('keydown', onKey)
        window.removeEventListener('keyup',   onKey)
        canvas.removeEventListener('touchstart', onTouchStart)
        canvas.removeEventListener('touchmove',  onTouchMove)
        canvas.removeEventListener('touchend',   onTouchEnd)
        submitResult(finalScore)
        return
      }

      // ── Draw ─────────────────────────────────────────────────────────────
      // Background gradient
      const bg = ctx.createLinearGradient(0, 0, 0, H)
      const t = Math.min(1, gameScore / 3000)
      const r1 = Math.round(10 + t * 5)
      const g1 = Math.round(8 + t * 2)
      const b1 = Math.round(20 + t * 15)
      bg.addColorStop(0, `rgb(${r1},${g1},${b1})`)
      bg.addColorStop(1, `rgb(${r1 + 5},${g1 + 3},${b1 + 8})`)
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, W, H)

      // Stars background dots
      ctx.fillStyle = 'rgba(255,255,255,0.4)'
      const seed = Math.floor(camY / 100)
      for (let i = 0; i < 25; i++) {
        const sx = ((seed * 73 + i * 137) % W + W) % W
        const sy = ((seed * 51 + i * 97 + i) % H + H) % H
        const r  = 0.5 + (i % 3) * 0.5
        ctx.beginPath()
        ctx.arc(sx, sy, r, 0, Math.PI * 2)
        ctx.fill()
      }

      // Platforms
      for (const p of plts) {
        const screenY = p.y - camY
        if (screenY > -20 && screenY < H + 20) {
          drawPlatform(ctx, { ...p, y: screenY })
        }
      }

      // Player
      drawPlayer(ctx, px, py, face, squish)

      // Score HUD
      ctx.fillStyle = 'rgba(0,0,0,0.4)'
      ctx.beginPath()
      ctx.roundRect(8, 8, 100, 36, 10)
      ctx.fill()
      ctx.fillStyle = '#fff'
      ctx.font = 'bold 18px system-ui'
      ctx.textAlign = 'left'
      ctx.fillText(`⭐ ${STARS_FOR_SCORE(gameScore)}`, 16, 31)

      ctx.fillStyle = 'rgba(0,0,0,0.4)'
      ctx.beginPath()
      ctx.roundRect(W - 110, 8, 102, 36, 10)
      ctx.fill()
      ctx.fillStyle = '#FFB830'
      ctx.font = 'bold 16px system-ui'
      ctx.textAlign = 'right'
      ctx.fillText(`${gameScore} м`, W - 12, 31)

      rafRef.current = requestAnimationFrame(loop)
    }

    rafRef.current = requestAnimationFrame(loop)

    return () => {
      running = false
      cancelAnimationFrame(rafRef.current)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('keyup',   onKey)
      canvas.removeEventListener('touchstart', onTouchStart)
      canvas.removeEventListener('touchmove',  onTouchMove)
      canvas.removeEventListener('touchend',   onTouchEnd)
    }
  }, [gstate, submitResult])

  // ── Canvas size ─────────────────────────────────────────────────────────────
  const canvasH = typeof window !== 'undefined' ? window.innerHeight - 60 : 600
  const canvasW = typeof window !== 'undefined' ? Math.min(window.innerWidth, 430) : 390

  // ── Render ──────────────────────────────────────────────────────────────────
  if (gstate === 'playing') {
    return (
      <canvas
        ref={canvasRef}
        width={canvasW}
        height={canvasH}
        style={{
          display: 'block',
          width: canvasW,
          height: canvasH,
          touchAction: 'none',
          userSelect: 'none',
        }}
      />
    )
  }

  const stars = status?.balance_stars ?? 0
  const isFree = status?.can_play_free ?? true

  return (
    <div className="page" style={{ paddingBottom: 80 }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #1E1428 0%, #141018 100%)',
        border: '1px solid rgba(255,107,43,.22)',
        borderRadius: 20, padding: '20px 18px', marginBottom: 12,
        textAlign: 'center', position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: -30, right: -30, width: 140, height: 140, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,107,43,.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{ fontSize: 52, marginBottom: 4 }}>🦎</div>
        <div style={{ fontWeight: 800, fontSize: 22, marginBottom: 4 }}>Лемур Джамп</div>
        <div style={{ fontSize: 13, color: 'var(--muted)' }}>Стрибай вище — отримуй зірки!</div>
        <div style={{ marginTop: 12, fontWeight: 700, color: 'var(--orange)', fontSize: 20 }}>
          ⭐ {stars}
        </div>
      </div>

      {/* Result card */}
      {gstate === 'done' && result && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(255,107,43,.15), rgba(255,107,43,.05))',
          border: '1px solid rgba(255,107,43,.4)',
          borderRadius: 16, padding: '18px 16px', marginBottom: 12, textAlign: 'center',
        }}>
          <div style={{ fontSize: 36, marginBottom: 6 }}>
            {result.score < 300 ? '😅' : result.score < 1200 ? '😊' : result.score < 2500 ? '🔥' : '🏆'}
          </div>
          <div style={{ fontWeight: 800, fontSize: 18 }}>Результат: {result.score} м</div>
          <div style={{ fontWeight: 800, fontSize: 28, color: 'var(--orange)', margin: '8px 0' }}>
            +{result.stars_earned} ⭐
          </div>
          <div style={{ fontSize: 13, color: 'var(--muted)' }}>
            Новий баланс: ⭐{result.new_balance}
          </div>
        </div>
      )}

      {err && (
        <div style={{
          background: 'rgba(255,60,60,.1)', border: '1px solid rgba(255,60,60,.3)',
          borderRadius: 12, padding: '10px 14px', marginBottom: 12,
          fontSize: 13, color: '#ff5555',
        }}>
          {err === 'insufficient_balance' ? '❌ Недостатньо зірок (потрібно ⭐10)' : `❌ ${err}`}
        </div>
      )}

      {/* Start button */}
      <button
        className="btn btn-primary"
        style={{ fontSize: 17, padding: '14px', marginBottom: 12, position: 'relative' }}
        disabled={gstate === 'loading' || gstate === 'submitting'}
        onClick={startGame}
      >
        {gstate === 'loading' || gstate === 'submitting'
          ? '⏳ Завантаження...'
          : gstate === 'done'
            ? isFree ? '🎮 Грати безкоштовно' : `🎮 Грати знову (⭐10)`
            : isFree ? '🎮 Безкоштовна гра!' : `🎮 Грати (⭐10)`}
      </button>

      {isFree && (
        <div style={{
          background: 'rgba(76,175,114,.1)', border: '1px solid rgba(76,175,114,.25)',
          borderRadius: 10, padding: '8px 12px', marginBottom: 12,
          fontSize: 13, color: '#4CAF72', textAlign: 'center',
        }}>
          🎁 Безкоштовна спроба на сьогодні!
        </div>
      )}

      {/* Score tiers */}
      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>Нагороди</div>
        {([
          [0,    300,  2,  '😅'],
          [300,  700,  5,  '🙂'],
          [700,  1200, 12, '😎'],
          [1200, 2000, 25, '🔥'],
          [2000, 3000, 45, '💫'],
          [3000, null, 75, '🏆'],
        ] as [number, number | null, number, string][]).map(([from, to, stars, icon]) => (
          <div key={from} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '7px 0', borderBottom: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 13, color: 'var(--muted)' }}>
              {icon} {from}м{to ? ` – ${to}м` : '+'}
            </div>
            <div style={{ fontWeight: 700, color: 'var(--orange)', fontSize: 14 }}>+{stars} ⭐</div>
          </div>
        ))}
      </div>

      {/* Controls hint */}
      <div className="card" style={{ marginTop: 10, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
        📱 Торкніться лівої/правої половини екрану для руху<br/>
        ⌨️ Або використовуйте ←→ клавіші
      </div>
    </div>
  )
}
