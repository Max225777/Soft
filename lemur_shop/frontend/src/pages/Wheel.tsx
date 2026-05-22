import { useState, useEffect, useRef, useCallback } from 'react'
import { api, wheelApi, type WheelResult } from '../api'

// ─── config ────────────────────────────────────────────────────────────────
const BET_OPTS = [10, 25, 50, 100, 250]
const SPIN_MS  = 5000
const LAPS     = 7

const NAMES = [
  'Олексій','Марія','Дмитро','Катя','Іван','Аня','Микола','Настя',
  'Вова','Юля','Сашко','Оля','Петро','Таня','Сергій','Ліза',
  'Артем','Віка','Богдан','Соня','Андрій','Даша',
]
const FLAGS  = ['🇺🇦','🇺🇦','🇺🇦','🇷🇺','🇵🇱','🇩🇪','🇧🇾','🇰🇿']
const COLORS = [
  '#FF6B2B',  // 0 = YOU
  '#2AABEE','#4CAF72','#FFD700','#E91E8C',
  '#9C27B0','#00BCD4','#FF5722','#8BC34A',
]

// ─── audio ─────────────────────────────────────────────────────────────────
function mkAudio() {
  try { return new (window.AudioContext || (window as any).webkitAudioContext)() }
  catch { return null }
}
function tick(ac: AudioContext) {
  try {
    const o = ac.createOscillator(), g = ac.createGain()
    o.connect(g); g.connect(ac.destination)
    o.type = 'triangle'; o.frequency.value = 500 + Math.random() * 300
    g.gain.setValueAtTime(0.12, ac.currentTime)
    g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.035)
    o.start(); o.stop(ac.currentTime + 0.035)
  } catch {}
}
function winSound(ac: AudioContext) {
  try {
    [523,659,784,1047,1318].forEach((f,i) => {
      const o = ac.createOscillator(), g = ac.createGain()
      o.connect(g); g.connect(ac.destination)
      o.type = 'sine'; o.frequency.value = f
      const t = ac.currentTime + i * 0.1
      g.gain.setValueAtTime(0.35, t)
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.35)
      o.start(t); o.stop(t + 0.35)
    })
  } catch {}
}
function loseSound(ac: AudioContext) {
  try {
    [380, 320, 270].forEach((f, i) => {
      const o = ac.createOscillator(), g = ac.createGain()
      o.connect(g); g.connect(ac.destination)
      o.type = 'sine'; o.frequency.value = f
      const t = ac.currentTime + i * 0.22
      g.gain.setValueAtTime(0.18, t)
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.28)
      o.start(t); o.stop(t + 0.28)
    })
  } catch {}
}

// ─── easing ────────────────────────────────────────────────────────────────
const easeOut = (t: number) => 1 - Math.pow(1 - t, 4)

// ─── types ─────────────────────────────────────────────────────────────────
interface Player { name: string; flag: string; bet: number; isYou: boolean }

// ─── draw wheel ────────────────────────────────────────────────────────────
function drawWheel(
  ctx: CanvasRenderingContext2D,
  players: Player[],
  rot: number,
  winIdx: number | null,
) {
  const W = ctx.canvas.width, H = ctx.canvas.height
  const cx = W / 2, cy = H / 2
  const R  = Math.min(cx, cy) - 6
  const total = players.reduce((s, p) => s + p.bet, 0)

  ctx.clearRect(0, 0, W, H)

  // outer shadow ring
  ctx.beginPath()
  ctx.arc(cx, cy, R + 8, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(0,0,0,0.45)'
  ctx.fill()

  let angle = rot
  players.forEach((p, i) => {
    const slice = (p.bet / total) * 2 * Math.PI
    const end   = angle + slice
    const col   = COLORS[i % COLORS.length]
    const isWin = i === winIdx

    ctx.save()
    if (isWin) { ctx.shadowColor = col; ctx.shadowBlur = 28 }
    if (p.isYou) { ctx.shadowColor = '#FFD700'; ctx.shadowBlur = 16 }

    // sector
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, R + (isWin ? 5 : 0), angle, end)
    ctx.closePath()
    ctx.fillStyle = col
    ctx.fill()

    // sector shine
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, R + (isWin ? 5 : 0), angle, angle + Math.min(slice * 0.25, 0.12))
    ctx.closePath()
    ctx.fillStyle = 'rgba(255,255,255,0.18)'
    ctx.fill()

    // border
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, R + (isWin ? 5 : 0), angle, end)
    ctx.closePath()
    ctx.strokeStyle = p.isYou ? 'rgba(255,215,0,0.8)' : 'rgba(0,0,0,0.35)'
    ctx.lineWidth   = p.isYou ? 2.5 : 1.5
    ctx.stroke()
    ctx.restore()

    // label
    if (slice > 0.15) {
      const mid = angle + slice / 2
      const lr  = R * 0.66
      ctx.save()
      ctx.translate(cx + Math.cos(mid) * lr, cy + Math.sin(mid) * lr)
      ctx.rotate(mid + Math.PI / 2)
      const fs = Math.min(13, Math.max(8, slice * 13))
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'

      if (p.isYou) {
        ctx.fillStyle = '#fff'
        ctx.font = `900 ${fs + 1}px system-ui`
        ctx.fillText('ВИ', 0, slice > 0.4 ? -7 : 0)
        if (slice > 0.4) {
          ctx.font = `bold ${fs}px system-ui`
          ctx.fillStyle = 'rgba(255,255,255,0.85)'
          ctx.fillText(`⭐${p.bet}`, 0, 8)
        }
      } else {
        ctx.fillStyle = 'rgba(255,255,255,0.88)'
        ctx.font = `bold ${fs}px system-ui`
        if (slice > 0.38) {
          ctx.fillText(p.flag, 0, -7)
          ctx.fillText(`⭐${p.bet}`, 0, 7)
        } else {
          ctx.fillText(`${p.bet}`, 0, 0)
        }
      }
      ctx.restore()
    }

    angle = end
  })

  // metallic rim layers
  ;[
    { r: R + 4, w: 5, c: 'rgba(220,200,255,0.22)' },
    { r: R + 2, w: 2, c: 'rgba(255,255,255,0.10)' },
    { r: R,     w: 2, c: 'rgba(150,120,200,0.25)' },
    { r: R - 3, w: 1, c: 'rgba(255,255,255,0.07)' },
  ].forEach(({ r, w, c }) => {
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.strokeStyle = c; ctx.lineWidth = w; ctx.stroke()
  })

  // center hub gradient
  const hub = ctx.createRadialGradient(cx - 6, cy - 6, 1, cx, cy, 28)
  hub.addColorStop(0, '#3a1560')
  hub.addColorStop(1, '#0d0516')
  ctx.beginPath(); ctx.arc(cx, cy, 28, 0, Math.PI * 2)
  ctx.fillStyle = hub; ctx.fill()
  ctx.beginPath(); ctx.arc(cx, cy, 28, 0, Math.PI * 2)
  ctx.strokeStyle = 'rgba(255,107,43,0.7)'; ctx.lineWidth = 2.5; ctx.stroke()

  ctx.font = '18px system-ui'
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
  ctx.fillText('🦎', cx, cy)
}

// ─── particles ─────────────────────────────────────────────────────────────
interface Pt { x:number;y:number;vx:number;vy:number;r:number;c:string;life:number;max:number }
const ptColors = ['#FF6B2B','#FFD700','#4CAF72','#2AABEE','#E91E8C','#fff','#FF5722']
function mkPts(cx: number, cy: number): Pt[] {
  return Array.from({ length: 90 }, () => {
    const a = Math.random() * Math.PI * 2, sp = 2 + Math.random() * 8, life = 55 + Math.random() * 65
    return { x: cx, y: cy, vx: Math.cos(a)*sp, vy: Math.sin(a)*sp - 4,
             r: 3 + Math.random() * 5, c: ptColors[Math.floor(Math.random()*ptColors.length)], life, max: life }
  })
}

// ─── component ─────────────────────────────────────────────────────────────
export default function WheelPage() {
  const cvRef  = useRef<HTMLCanvasElement>(null)
  const ptRef  = useRef<HTMLCanvasElement>(null)
  const rotRef = useRef(0)
  const rafRef = useRef(0)
  const ptRaf  = useRef(0)
  const acRef  = useRef<AudioContext | null>(null)
  const prevR  = useRef(0)
  const tickA  = useRef(0)
  const TICK   = (2 * Math.PI) / 14

  const [balance,  setBalance ] = useState<number | null>(null)
  const [pot,      setPot     ] = useState(0)
  const [bet,      setBet     ] = useState(50)
  const [players,  setPlayers ] = useState<Player[]>([])
  const [status,   setStatus  ] = useState<'idle'|'loading'|'spinning'|'done'>('idle')
  const [result,   setResult  ] = useState<WheelResult | null>(null)
  const [feed,     setFeed    ] = useState('')

  const genPlayers = useCallback((myBet: number): Player[] => {
    const n = 3 + Math.floor(Math.random() * 4)
    const fake: Player[] = Array.from({ length: n }, () => ({
      name: NAMES[Math.floor(Math.random()*NAMES.length)],
      flag: FLAGS[Math.floor(Math.random()*FLAGS.length)],
      bet:  Math.max(10, Math.round((myBet * (0.4 + Math.random()*1.4)) / 10) * 10),
      isYou: false,
    }))
    return [{ name:'ВИ', flag:'🟠', bet: myBet, isYou: true }, ...fake]
  }, [])

  const redraw = useCallback((ps: Player[], win: number | null) => {
    const cv = cvRef.current; if (!cv) return
    drawWheel(cv.getContext('2d')!, ps, rotRef.current, win)
  }, [])

  // init
  useEffect(() => {
    api.me().then(m => setBalance(m.balance_stars)).catch(() => {})
    wheelApi.pot().then(p => setPot(p.pot_stars)).catch(() => {})
    acRef.current = mkAudio()
  }, [])

  // regenerate players on bet change
  useEffect(() => {
    const ps = genPlayers(bet)
    setPlayers(ps)
    redraw(ps, null)
  }, [bet, genPlayers, redraw])

  // fake activity feed
  useEffect(() => {
    const msgs = [
      () => `${FLAGS[Math.floor(Math.random()*FLAGS.length)]} ${NAMES[Math.floor(Math.random()*NAMES.length)]} ставить ⭐${BET_OPTS[Math.floor(Math.random()*BET_OPTS.length)]}`,
      () => `🎉 ${NAMES[Math.floor(Math.random()*NAMES.length)]} виграв ⭐${30 + Math.floor(Math.random()*200)}`,
      () => `${FLAGS[Math.floor(Math.random()*FLAGS.length)]} ${NAMES[Math.floor(Math.random()*NAMES.length)]} приєднався`,
      () => `🔥 Банк вже ⭐${pot + Math.floor(Math.random()*50)}!`,
    ]
    setFeed(msgs[Math.floor(Math.random()*msgs.length)]())
    const id = setInterval(() => setFeed(msgs[Math.floor(Math.random()*msgs.length)]()), 2800 + Math.random()*2000)
    return () => clearInterval(id)
  }, [pot])

  function doParticles() {
    const cv = ptRef.current; if (!cv) return
    const ctx = cv.getContext('2d')!
    let pts = mkPts(cv.width/2, cv.height/2)
    cancelAnimationFrame(ptRaf.current)
    function frame() {
      ctx.clearRect(0,0,cv.width,cv.height)
      pts = pts.filter(p => p.life > 0)
      pts.forEach(p => {
        p.x+=p.vx; p.y+=p.vy; p.vy+=0.18; p.vx*=0.97; p.life--
        const a = p.life/p.max
        ctx.beginPath(); ctx.arc(p.x,p.y,p.r*a,0,Math.PI*2)
        ctx.fillStyle=p.c; ctx.globalAlpha=a; ctx.fill(); ctx.globalAlpha=1
      })
      if (pts.length>0) ptRaf.current=requestAnimationFrame(frame)
    }
    ptRaf.current=requestAnimationFrame(frame)
  }

  function spinTo(won: boolean, ps: Player[], done: () => void) {
    const cv = cvRef.current!; const ctx = cv.getContext('2d')!
    const total = ps.reduce((s,p)=>s+p.bet,0)
    const slices = ps.map(p=>(p.bet/total)*2*Math.PI)
    const tIdx   = won ? 0 : 1 + Math.floor(Math.random()*(ps.length-1))
    const sStart = slices.slice(0,tIdx).reduce((a,b)=>a+b,0)
    const sMid   = sStart + slices[tIdx]/2

    const base = -Math.PI/2 - sMid
    const cur  = rotRef.current
    const k    = Math.ceil((cur + LAPS*2*Math.PI - base) / (2*Math.PI))
    const tRot = base + k*2*Math.PI

    const t0 = performance.now()
    const s0 = cur
    prevR.current = cur; tickA.current = 0
    cancelAnimationFrame(rafRef.current)

    function frame(now: number) {
      const t   = Math.min((now-t0)/SPIN_MS, 1)
      const rot = s0 + (tRot - s0) * easeOut(t)

      // ticks
      const d = Math.abs(rot - prevR.current)
      tickA.current += d
      const n = Math.floor(tickA.current / TICK)
      if (n > 0) { if (acRef.current) tick(acRef.current); tickA.current -= n*TICK }
      prevR.current = rot

      rotRef.current = rot
      drawWheel(ctx, ps, rot, t>=1 ? tIdx : null)

      if (t < 1) { rafRef.current = requestAnimationFrame(frame) }
      else {
        if (won) { if (acRef.current) winSound(acRef.current); doParticles() }
        else     {  if (acRef.current) loseSound(acRef.current) }
        done()
      }
    }
    rafRef.current = requestAnimationFrame(frame)
  }

  async function handleSpin() {
    if (status==='loading'||status==='spinning') return
    if (acRef.current?.state==='suspended') acRef.current.resume().catch(()=>{})
    setStatus('loading'); setResult(null)
    const ps = genPlayers(bet)
    setPlayers(ps); redraw(ps, null)
    try {
      const res = await wheelApi.spin(bet)
      setResult(res); setBalance(res.new_balance); setPot(res.pot_stars)
      setStatus('spinning')
      spinTo(res.player_won, ps, () => setStatus('done'))
    } catch (e: any) {
      setStatus('idle'); alert(e.message || 'Помилка')
    }
  }

  const spinning = status==='loading'||status==='spinning'
  const noFunds  = balance!==null && balance < bet
  const potWin   = Math.round(pot * 0.7)
  const SIZE     = 290

  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', padding:'10px 10px 20px' }}>

      {/* header */}
      <div style={{ width:'100%', display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
        <div style={{ fontSize:17, fontWeight:800 }}>🎡 Колесо удачі</div>
        <div style={{
          fontSize:13, fontWeight:700, padding:'4px 11px', borderRadius:20,
          background:'rgba(255,215,0,.1)', border:'1px solid rgba(255,215,0,.3)',
        }}>⭐ {balance ?? '…'}</div>
      </div>

      {/* jackpot banner */}
      <div style={{
        width:'100%', maxWidth:SIZE, borderRadius:16, marginBottom:12, padding:'12px 16px',
        background:'linear-gradient(135deg,rgba(255,107,43,.18),rgba(255,215,0,.10))',
        border:'1px solid rgba(255,215,0,.35)',
        boxShadow: pot > 50 ? '0 0 24px rgba(255,215,0,.18)' : 'none',
        display:'flex', alignItems:'center', justifyContent:'space-between',
      }}>
        <div>
          <div style={{ fontSize:10, color:'var(--muted)', letterSpacing:1, textTransform:'uppercase', marginBottom:2 }}>
            💰 Поточний банк
          </div>
          <div style={{
            fontSize:28, fontWeight:900, lineHeight:1,
            background:'linear-gradient(90deg,#FF6B2B,#FFD700)',
            WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent',
          }}>
            ⭐ {pot}
          </div>
        </div>
        <div style={{ textAlign:'right' }}>
          <div style={{ fontSize:10, color:'var(--muted)', marginBottom:2 }}>Переможець отримає</div>
          <div style={{ fontSize:18, fontWeight:800, color:'#4CAF72' }}>≈ ⭐{potWin}</div>
        </div>
      </div>

      {/* wheel + particles overlay */}
      <div style={{ position:'relative', marginBottom:10 }}>
        {/* pointer */}
        <div style={{
          position:'absolute', top:-2, left:'50%', transform:'translate(-50%,-100%)',
          zIndex:3,
        }}>
          <svg width="24" height="28" viewBox="0 0 24 28">
            <defs>
              <linearGradient id="pg" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#FF9950"/>
                <stop offset="100%" stopColor="#FF3300"/>
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="2" result="blur"/>
                <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
              </filter>
            </defs>
            <polygon points="12,28 0,0 24,0" fill="url(#pg)" filter="url(#glow)"/>
            <polygon points="12,28 0,0 24,0" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1"/>
          </svg>
        </div>

        {/* particle canvas (overlay) */}
        <canvas ref={ptRef} width={SIZE} height={SIZE}
          style={{ position:'absolute', top:0, left:0, pointerEvents:'none', zIndex:2 }}
        />

        {/* wheel canvas */}
        <canvas ref={cvRef} width={SIZE} height={SIZE}
          style={{ display:'block', borderRadius:'50%',
            boxShadow:'0 0 40px rgba(100,50,200,.35), 0 8px 32px rgba(0,0,0,.6)' }}
        />
      </div>

      {/* players legend */}
      <div style={{
        width:'100%', maxWidth:SIZE, display:'flex', flexWrap:'wrap',
        gap:5, marginBottom:10, justifyContent:'center',
      }}>
        {players.map((p, i) => (
          <div key={i} style={{
            display:'flex', alignItems:'center', gap:4, padding:'4px 9px',
            borderRadius:20, fontSize:11, fontWeight:700,
            background: p.isYou ? 'rgba(255,107,43,.2)' : 'rgba(255,255,255,.06)',
            border: p.isYou ? '1px solid rgba(255,107,43,.5)' : '1px solid rgba(255,255,255,.08)',
            color: p.isYou ? '#FF9950' : 'var(--muted)',
          }}>
            <span style={{
              width:8, height:8, borderRadius:'50%', flexShrink:0,
              background: COLORS[i % COLORS.length],
              boxShadow: p.isYou ? `0 0 6px ${COLORS[0]}` : 'none',
            }}/>
            {p.isYou ? 'ВИ' : `${p.flag} ${p.name.slice(0,5)}`}
            <span style={{ opacity:.7 }}>⭐{p.bet}</span>
          </div>
        ))}
      </div>

      {/* result card */}
      {status==='done' && result && (
        <div style={{
          width:'100%', maxWidth:SIZE, borderRadius:16, padding:'14px 18px',
          marginBottom:10, textAlign:'center',
          background: result.player_won
            ? 'linear-gradient(135deg,rgba(76,175,72,.22),rgba(76,175,72,.05))'
            : 'rgba(255,255,255,.04)',
          border:`1px solid ${result.player_won ? 'rgba(76,175,72,.55)' : 'rgba(255,255,255,.1)'}`,
          boxShadow: result.player_won ? '0 0 30px rgba(76,175,72,.2)' : 'none',
          animation: 'fadeIn .4s ease',
        }}>
          {result.player_won ? (
            <>
              <div style={{ fontSize:38, marginBottom:2 }}>🎉</div>
              <div style={{ fontSize:22, fontWeight:900, color:'#4CAF72' }}>Ти виграв!</div>
              <div style={{ fontSize:17, marginTop:4, fontWeight:700 }}>+⭐{result.payout}</div>
              <div style={{ fontSize:12, color:'var(--muted)', marginTop:3 }}>
                Баланс: ⭐{result.new_balance}
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize:38, marginBottom:2 }}>😔</div>
              <div style={{ fontSize:18, fontWeight:800, color:'var(--muted)' }}>Не пощастило</div>
              <div style={{ fontSize:12, color:'var(--muted)', marginTop:3 }}>
                Твоя ставка поповнила банк · зараз у банку ⭐{result.pot_stars}
              </div>
              <div style={{ fontSize:12, color:'var(--muted)', marginTop:2 }}>
                Баланс: ⭐{result.new_balance}
              </div>
            </>
          )}
        </div>
      )}

      {/* bet selector */}
      {!spinning && (
        <div style={{ display:'flex', gap:6, marginBottom:10, flexWrap:'wrap', justifyContent:'center' }}>
          {BET_OPTS.map(b => (
            <button key={b} onClick={()=>setBet(b)} style={{
              padding:'6px 14px', borderRadius:20, fontSize:13, fontWeight:800,
              background: bet===b ? 'var(--accent)' : 'rgba(255,255,255,.07)',
              color: bet===b ? '#fff' : 'var(--muted)',
              border: bet===b ? '1px solid transparent' : '1px solid rgba(255,255,255,.1)',
              cursor:'pointer', transition:'all .15s',
              boxShadow: bet===b ? '0 0 12px rgba(255,107,43,.4)' : 'none',
            }}>⭐{b}</button>
          ))}
        </div>
      )}

      {/* spin button */}
      <button
        className="btn btn-primary"
        onClick={spinning ? undefined : handleSpin}
        disabled={spinning || noFunds}
        style={{
          width:'100%', maxWidth:SIZE, fontSize:16, fontWeight:900, padding:'15px 0',
          boxShadow: !spinning && !noFunds ? '0 0 24px rgba(255,107,43,.5)' : 'none',
          transition:'box-shadow .3s',
        }}
      >
        {status==='loading'  ? '⏳ Підключення...' :
         status==='spinning' ? '🎡 Крутиться...'   :
         `🎡 Крутити  ⭐${bet}`}
      </button>

      {noFunds && !spinning && (
        <div style={{ fontSize:12, color:'#FF5252', marginTop:6 }}>
          Недостатньо зірок
        </div>
      )}

      {/* live activity feed */}
      {feed && (
        <div style={{
          marginTop:12, fontSize:11, color:'var(--muted)',
          background:'rgba(255,255,255,.04)', border:'1px solid rgba(255,255,255,.07)',
          borderRadius:20, padding:'5px 14px', maxWidth:SIZE,
          overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap',
          animation:'fadeIn .5s ease',
        }}>
          🔴 live · {feed}
        </div>
      )}

      <div style={{ fontSize:11, color:'var(--muted)', marginTop:8, textAlign:'center', maxWidth:SIZE, lineHeight:1.5 }}>
        Всі ставки йдуть у банк · переможець забирає 70%
      </div>

      <style>{`
        @keyframes fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:none} }
      `}</style>
    </div>
  )
}
