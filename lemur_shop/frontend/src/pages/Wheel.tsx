import { useState, useEffect, useRef, useCallback } from 'react'
import { api, wheelApi, type WheelRoomInfo, type WheelParticipantInfo } from '../api'

// ─── config ────────────────────────────────────────────────────────────────
const STAKES   = [10, 25, 50, 100]
const SIZES    = [2, 5, 10]
const SPIN_MS  = 4500
const LAPS     = 6
const POLL_MS  = 2000

const COLORS = [
  '#FF6B2B','#2AABEE','#4CAF72','#FFD700',
  '#E91E8C','#9C27B0','#00BCD4','#FF5722',
  '#8BC34A','#F44336',
]

// ─── audio ─────────────────────────────────────────────────────────────────
function mkAC() {
  try { return new (window.AudioContext || (window as any).webkitAudioContext)() } catch { return null }
}
function playTick(ac: AudioContext) {
  try {
    const o = ac.createOscillator(), g = ac.createGain()
    o.connect(g); g.connect(ac.destination)
    o.type = 'triangle'; o.frequency.value = 480 + Math.random() * 280
    g.gain.setValueAtTime(0.1, ac.currentTime)
    g.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.03)
    o.start(); o.stop(ac.currentTime + 0.03)
  } catch {}
}
function playWin(ac: AudioContext) {
  try {
    [523, 659, 784, 1047, 1318].forEach((f, i) => {
      const o = ac.createOscillator(), g = ac.createGain()
      o.connect(g); g.connect(ac.destination)
      o.type = 'sine'; o.frequency.value = f
      const t = ac.currentTime + i * 0.1
      g.gain.setValueAtTime(0.3, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.35)
      o.start(t); o.stop(t + 0.35)
    })
  } catch {}
}
function playLose(ac: AudioContext) {
  try {
    [380, 320, 260].forEach((f, i) => {
      const o = ac.createOscillator(), g = ac.createGain()
      o.connect(g); g.connect(ac.destination)
      o.type = 'sine'; o.frequency.value = f
      const t = ac.currentTime + i * 0.2
      g.gain.setValueAtTime(0.15, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.25)
      o.start(t); o.stop(t + 0.25)
    })
  } catch {}
}

// ─── easing ────────────────────────────────────────────────────────────────
const easeOut = (t: number) => 1 - Math.pow(1 - t, 4)

// ─── draw wheel ────────────────────────────────────────────────────────────
function drawWheel(
  ctx: CanvasRenderingContext2D,
  parts: WheelParticipantInfo[],
  rot: number,
  winIdx: number | null,
) {
  const W = ctx.canvas.width, H = ctx.canvas.height, cx = W/2, cy = H/2
  const R = Math.min(cx,cy) - 8
  const n = parts.length
  const slice = (2*Math.PI) / n

  ctx.clearRect(0,0,W,H)

  // outer shadow
  ctx.beginPath(); ctx.arc(cx,cy,R+10,0,Math.PI*2)
  ctx.fillStyle='rgba(0,0,0,0.5)'; ctx.fill()

  parts.forEach((p, i) => {
    const a = rot + i*slice, end = a + slice
    const col = COLORS[i % COLORS.length]
    const isWin = i===winIdx

    ctx.save()
    if (isWin || p.is_you) { ctx.shadowColor = p.is_you ? '#FFD700' : col; ctx.shadowBlur = 22 }
    ctx.beginPath(); ctx.moveTo(cx,cy); ctx.arc(cx,cy, isWin?R+6:R, a, end); ctx.closePath()
    ctx.fillStyle = col; ctx.fill()
    // shine
    ctx.beginPath(); ctx.moveTo(cx,cy)
    ctx.arc(cx,cy, isWin?R+6:R, a, a+Math.min(slice*0.28,0.14)); ctx.closePath()
    ctx.fillStyle='rgba(255,255,255,0.16)'; ctx.fill()
    // border
    ctx.beginPath(); ctx.moveTo(cx,cy); ctx.arc(cx,cy, isWin?R+6:R, a, end); ctx.closePath()
    ctx.strokeStyle = p.is_you?'rgba(255,215,0,0.9)':'rgba(0,0,0,0.3)'
    ctx.lineWidth = p.is_you?2.5:1.5; ctx.stroke()
    ctx.restore()

    // label
    if (slice > 0.22) {
      const mid = a + slice/2, lr = R*0.66
      ctx.save()
      ctx.translate(cx+Math.cos(mid)*lr, cy+Math.sin(mid)*lr)
      ctx.rotate(mid + Math.PI/2)
      const fs = Math.min(13, Math.max(8, slice*12))
      ctx.textAlign='center'; ctx.textBaseline='middle'
      ctx.fillStyle='rgba(255,255,255,0.92)'
      ctx.font = `bold ${fs}px system-ui`
      if (p.is_you) {
        ctx.fillStyle='#fff'; ctx.font=`900 ${fs+1}px system-ui`
        ctx.fillText('ВИ', 0, slice>0.8?-7:0)
      } else {
        const label = p.name.length > 8 ? p.name.slice(0,7)+'…' : p.name
        ctx.fillText(label, 0, 0)
      }
      ctx.restore()
    }
  })

  // rim layers
  ;[{r:R+5,w:5,c:'rgba(200,180,240,0.2)'},{r:R+2,w:2,c:'rgba(255,255,255,0.1)'},{r:R,w:2,c:'rgba(140,100,200,0.22)'}]
    .forEach(({r,w,c})=>{ ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.strokeStyle=c; ctx.lineWidth=w; ctx.stroke() })

  // center hub
  const hub = ctx.createRadialGradient(cx-5,cy-5,1,cx,cy,26)
  hub.addColorStop(0,'#3a1560'); hub.addColorStop(1,'#0d0516')
  ctx.beginPath(); ctx.arc(cx,cy,26,0,Math.PI*2); ctx.fillStyle=hub; ctx.fill()
  ctx.beginPath(); ctx.arc(cx,cy,26,0,Math.PI*2)
  ctx.strokeStyle='rgba(255,107,43,0.65)'; ctx.lineWidth=2.5; ctx.stroke()
  ctx.font='17px system-ui'; ctx.textAlign='center'; ctx.textBaseline='middle'
  ctx.fillText('🦎',cx,cy)
}

// ─── particles ─────────────────────────────────────────────────────────────
interface Pt{x:number;y:number;vx:number;vy:number;r:number;c:string;life:number;max:number}
const ptC=['#FF6B2B','#FFD700','#4CAF72','#2AABEE','#E91E8C','#fff']
function mkPts(cx:number,cy:number):Pt[]{
  return Array.from({length:80},()=>{
    const a=Math.random()*Math.PI*2,sp=2+Math.random()*8,life=50+Math.random()*60
    return{x:cx,y:cy,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp-3,r:3+Math.random()*5,
           c:ptC[Math.floor(Math.random()*ptC.length)],life,max:life}
  })
}

// ─── component ─────────────────────────────────────────────────────────────
type Screen = 'lobby' | 'waiting' | 'spinning' | 'result'

export default function WheelPage() {
  const cvRef   = useRef<HTMLCanvasElement>(null)
  const ptRef   = useRef<HTMLCanvasElement>(null)
  const rotRef  = useRef(0)
  const rafRef  = useRef(0)
  const ptRaf   = useRef(0)
  const acRef   = useRef<AudioContext|null>(null)
  const prevR   = useRef(0)
  const tickA   = useRef(0)
  const pollRef = useRef<ReturnType<typeof setInterval>|null>(null)
  const TICK    = (2*Math.PI)/14

  const [screen,  setScreen ] = useState<Screen>('lobby')
  const [balance, setBalance] = useState<number|null>(null)
  const [stake,   setStake  ] = useState(25)
  const [size,    setSize   ] = useState(5)
  const [lobby,   setLobby  ] = useState<{stake:number;max_players:number;waiting:number}[]>([])
  const [room,    setRoom   ] = useState<WheelRoomInfo|null>(null)
  const [joining, setJoining] = useState(false)

  // lobby data
  const refreshLobby = useCallback(() => {
    wheelApi.lobby().then(setLobby).catch(()=>{})
  }, [])

  useEffect(() => {
    api.me().then(m=>setBalance(m.balance_stars)).catch(()=>{})
    acRef.current = mkAC()
    refreshLobby()
    const t = setInterval(refreshLobby, 5000)
    return () => clearInterval(t)
  }, [refreshLobby])

  // initial wheel draw (placeholder)
  useEffect(() => {
    const cv = cvRef.current; if (!cv) return
    const ctx = cv.getContext('2d')!
    const n = size
    const fake: WheelParticipantInfo[] = Array.from({length:n},(_,i)=>({
      name: i===0?'ВИ':'?', is_you:i===0, is_bot:false
    }))
    drawWheel(ctx, fake, rotRef.current, null)
  }, [size])

  // polling room status when waiting
  useEffect(() => {
    if (screen === 'waiting' && room) {
      pollRef.current = setInterval(async () => {
        try {
          const r = await wheelApi.room(room.id)
          setRoom(r)
          if (r.status === 'done') {
            clearInterval(pollRef.current!)
            setBalance(r.new_balance)
            setScreen('spinning')
            spinWheel(r)
          }
        } catch {}
      }, POLL_MS)
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [screen, room?.id])

  function doParticles() {
    const cv = ptRef.current; if (!cv) return
    const ctx = cv.getContext('2d')!
    let pts = mkPts(cv.width/2, cv.height/2)
    cancelAnimationFrame(ptRaf.current)
    function frame() {
      ctx.clearRect(0,0,cv.width,cv.height)
      pts = pts.filter(p=>p.life>0)
      pts.forEach(p=>{
        p.x+=p.vx;p.y+=p.vy;p.vy+=0.18;p.vx*=0.97;p.life--
        const a=p.life/p.max
        ctx.beginPath();ctx.arc(p.x,p.y,p.r*a,0,Math.PI*2)
        ctx.fillStyle=p.c;ctx.globalAlpha=a;ctx.fill();ctx.globalAlpha=1
      })
      if(pts.length>0) ptRaf.current=requestAnimationFrame(frame)
    }
    ptRaf.current=requestAnimationFrame(frame)
  }

  function spinWheel(r: WheelRoomInfo) {
    const cv = cvRef.current!; const ctx = cv.getContext('2d')!
    const parts = r.participants
    const winIdx = parts.findIndex(p => p.name === r.winner_name && !p.is_you)
    const trueWinIdx = r.winner_is_you
      ? parts.findIndex(p=>p.is_you)
      : (winIdx>=0 ? winIdx : Math.floor(Math.random()*parts.length))

    const n = parts.length
    const slice = (2*Math.PI)/n
    const sMid = trueWinIdx*slice + slice/2
    const base = -Math.PI/2 - sMid
    const cur  = rotRef.current
    const k    = Math.ceil((cur + LAPS*2*Math.PI - base)/(2*Math.PI))
    const tRot = base + k*2*Math.PI
    const s0   = cur
    const t0   = performance.now()
    prevR.current = cur; tickA.current = 0
    cancelAnimationFrame(rafRef.current)

    function frame(now:number){
      const t   = Math.min((now-t0)/SPIN_MS,1)
      const rot = s0 + (tRot-s0)*easeOut(t)
      const d   = Math.abs(rot - prevR.current)
      tickA.current += d
      const n2 = Math.floor(tickA.current/TICK)
      if(n2>0){ if(acRef.current) playTick(acRef.current); tickA.current-=n2*TICK }
      prevR.current = rot
      rotRef.current = rot
      drawWheel(ctx, parts, rot, t>=1 ? trueWinIdx : null)
      if(t<1){ rafRef.current=requestAnimationFrame(frame) }
      else {
        if(r.winner_is_you){ if(acRef.current) playWin(acRef.current); doParticles() }
        else { if(acRef.current) playLose(acRef.current) }
        setScreen('result')
      }
    }
    rafRef.current=requestAnimationFrame(frame)
  }

  async function handleJoin() {
    if (joining) return
    if (acRef.current?.state==='suspended') acRef.current.resume().catch(()=>{})
    setJoining(true)
    try {
      const { room_id } = await wheelApi.join(stake, size)
      const r = await wheelApi.room(room_id)
      setRoom(r)
      setBalance(b => b!==null ? b - stake : b)
      if (r.status === 'done') {
        setScreen('spinning')
        spinWheel(r)
      } else {
        setScreen('waiting')
      }
    } catch (e: any) {
      alert(e.message || 'Помилка')
    } finally {
      setJoining(false)
    }
  }

  function handleBack() {
    setScreen('lobby')
    setRoom(null)
    refreshLobby()
    api.me().then(m=>setBalance(m.balance_stars)).catch(()=>{})
  }

  const waitingFor = lobby.find(l=>l.stake===stake&&l.max_players===size)?.waiting ?? 0
  const pool = stake * size
  const win  = Math.round(pool * 0.75)
  const noFunds = balance!==null && balance < stake
  const SIZE = 280

  // ─── lobby screen ────────────────────────────────────────────────────────
  if (screen === 'lobby') return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'12px 12px 24px'}}>

      <div style={{width:'100%',display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
        <div style={{fontSize:17,fontWeight:800}}>🎡 Колесо удачі</div>
        <div style={{fontSize:13,fontWeight:700,padding:'4px 11px',borderRadius:20,
          background:'rgba(255,215,0,.1)',border:'1px solid rgba(255,215,0,.3)'}}>
          ⭐ {balance??'…'}
        </div>
      </div>

      {/* stake */}
      <div style={{width:'100%',marginBottom:14}}>
        <div style={{fontSize:12,color:'var(--muted)',marginBottom:7,fontWeight:600}}>СТАВКА</div>
        <div style={{display:'flex',gap:7,flexWrap:'wrap'}}>
          {STAKES.map(s=>(
            <button key={s} onClick={()=>setStake(s)} style={{
              padding:'8px 16px',borderRadius:20,fontSize:14,fontWeight:800,
              background:stake===s?'var(--accent)':'rgba(255,255,255,.07)',
              color:stake===s?'#fff':'var(--muted)',
              border:stake===s?'none':'1px solid rgba(255,255,255,.1)',
              cursor:'pointer',boxShadow:stake===s?'0 0 14px rgba(255,107,43,.4)':'none',
            }}>⭐{s}</button>
          ))}
        </div>
      </div>

      {/* size */}
      <div style={{width:'100%',marginBottom:16}}>
        <div style={{fontSize:12,color:'var(--muted)',marginBottom:7,fontWeight:600}}>КІЛЬКІСТЬ ГРАВЦІВ</div>
        <div style={{display:'flex',gap:7}}>
          {SIZES.map(n=>(
            <button key={n} onClick={()=>setSize(n)} style={{
              flex:1,padding:'10px 0',borderRadius:14,fontSize:14,fontWeight:800,
              background:size===n?'rgba(42,171,238,.2)':'rgba(255,255,255,.05)',
              color:size===n?'#2AABEE':'var(--muted)',
              border:`1px solid ${size===n?'rgba(42,171,238,.5)':'rgba(255,255,255,.08)'}`,
              cursor:'pointer',
            }}>
              👥 {n}
            </button>
          ))}
        </div>
      </div>

      {/* info card */}
      <div style={{
        width:'100%',borderRadius:16,padding:'14px 18px',marginBottom:16,
        background:'linear-gradient(135deg,rgba(255,107,43,.12),rgba(42,171,238,.08))',
        border:'1px solid rgba(255,255,255,.1)',
      }}>
        <div style={{display:'flex',justifyContent:'space-between',marginBottom:8}}>
          <div>
            <div style={{fontSize:11,color:'var(--muted)',marginBottom:2}}>Загальний пул</div>
            <div style={{fontSize:20,fontWeight:900}}>⭐ {pool}</div>
          </div>
          <div style={{textAlign:'right'}}>
            <div style={{fontSize:11,color:'var(--muted)',marginBottom:2}}>Виграш</div>
            <div style={{fontSize:20,fontWeight:900,color:'#4CAF72'}}>⭐ {win}</div>
          </div>
        </div>
        <div style={{
          display:'flex',alignItems:'center',gap:6,
          background:'rgba(255,255,255,.05)',borderRadius:10,padding:'8px 12px',
        }}>
          <div style={{width:8,height:8,borderRadius:'50%',background:'#4CAF72',
            boxShadow:'0 0 6px #4CAF72',flexShrink:0}}/>
          <div style={{fontSize:12,color:'var(--muted)'}}>
            {waitingFor > 0
              ? <><strong style={{color:'var(--text)'}}>{waitingFor}/{size}</strong> вже чекають</>
              : 'Поки нікого · будь першим!'}
          </div>
        </div>
      </div>

      {/* wheel preview */}
      <div style={{position:'relative',marginBottom:14}}>
        <div style={{position:'absolute',top:0,left:'50%',transform:'translate(-50%,-100%)',zIndex:2}}>
          <svg width="22" height="26" viewBox="0 0 22 26">
            <defs>
              <linearGradient id="pg2" x1="0%"y1="0%"x2="0%"y2="100%">
                <stop offset="0%" stopColor="#FF9950"/>
                <stop offset="100%" stopColor="#FF3300"/>
              </linearGradient>
            </defs>
            <polygon points="11,26 0,0 22,0" fill="url(#pg2)"/>
          </svg>
        </div>
        <canvas ref={cvRef} width={SIZE} height={SIZE}
          style={{display:'block',borderRadius:'50%',
            boxShadow:'0 0 36px rgba(100,50,200,.3),0 8px 28px rgba(0,0,0,.5)'}}/>
        <canvas ref={ptRef} width={SIZE} height={SIZE}
          style={{position:'absolute',top:0,left:0,pointerEvents:'none',borderRadius:'50%'}}/>
      </div>

      <button className="btn btn-primary"
        onClick={handleJoin}
        disabled={joining||noFunds}
        style={{width:'100%',maxWidth:SIZE,fontSize:16,fontWeight:900,padding:'15px 0',
          boxShadow:!noFunds?'0 0 22px rgba(255,107,43,.45)':'none'}}>
        {joining?'⏳ Підключення...':`🎡 Приєднатись  ⭐${stake}`}
      </button>

      {noFunds&&<div style={{fontSize:12,color:'#FF5252',marginTop:6}}>Недостатньо зірок</div>}

      <div style={{fontSize:11,color:'var(--muted)',marginTop:10,textAlign:'center',lineHeight:1.5}}>
        Переможець забирає 75% пулу · хаус 25%
      </div>
    </div>
  )

  // ─── waiting screen ───────────────────────────────────────────────────────
  if (screen === 'waiting' && room) {
    const joined = room.participants.length
    return (
      <div style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'14px 12px 24px'}}>
        <div style={{width:'100%',display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:14}}>
          <div style={{fontSize:16,fontWeight:800}}>⏳ Очікуємо гравців</div>
          <div style={{fontSize:13,fontWeight:700,padding:'4px 11px',borderRadius:20,
            background:'rgba(255,215,0,.1)',border:'1px solid rgba(255,215,0,.3)'}}>
            ⭐ {balance??'…'}
          </div>
        </div>

        {/* progress */}
        <div style={{
          width:'100%',maxWidth:SIZE,borderRadius:16,padding:'14px 18px',marginBottom:16,
          background:'rgba(255,255,255,.04)',border:'1px solid rgba(255,255,255,.1)',
        }}>
          <div style={{display:'flex',justifyContent:'space-between',marginBottom:10}}>
            <div style={{fontSize:14,fontWeight:700}}>
              <span style={{color:'#2AABEE',fontSize:22,fontWeight:900}}>{joined}</span>
              <span style={{color:'var(--muted)'}}> / {room.max_players}</span>
            </div>
            <div style={{fontSize:13,color:'var(--muted)'}}>Пул: ⭐{room.stake * room.max_players}</div>
          </div>
          {/* progress bar */}
          <div style={{height:6,borderRadius:6,background:'rgba(255,255,255,.08)',overflow:'hidden'}}>
            <div style={{height:'100%',borderRadius:6,
              background:'linear-gradient(90deg,#FF6B2B,#FFD700)',
              width:`${(joined/room.max_players)*100}%`,transition:'width .5s'}}/>
          </div>
        </div>

        {/* slots */}
        <div style={{width:'100%',maxWidth:SIZE,display:'flex',flexDirection:'column',gap:8,marginBottom:16}}>
          {Array.from({length:room.max_players},(_,i)=>{
            const p = room.participants[i]
            return (
              <div key={i} style={{
                display:'flex',alignItems:'center',gap:12,
                padding:'10px 14px',borderRadius:12,
                background: p ? (p.is_you?'rgba(255,107,43,.12)':'rgba(255,255,255,.05)') : 'rgba(255,255,255,.03)',
                border:`1px solid ${p?(p.is_you?'rgba(255,107,43,.4)':'rgba(255,255,255,.08)'):'rgba(255,255,255,.05)'}`,
                transition:'all .3s',
              }}>
                <div style={{
                  width:36,height:36,borderRadius:'50%',flexShrink:0,
                  background: p ? COLORS[i%COLORS.length] : 'rgba(255,255,255,.06)',
                  display:'flex',alignItems:'center',justifyContent:'center',
                  fontSize:14,fontWeight:800,
                  boxShadow: p?.is_you ? '0 0 12px rgba(255,107,43,.5)' : 'none',
                }}>
                  {p ? (p.is_you?'ВИ':p.name.charAt(0)) : '?'}
                </div>
                <div>
                  <div style={{fontSize:14,fontWeight:700,color:p?.is_you?'#FF9950':'var(--text)'}}>
                    {p ? p.name : <span style={{color:'var(--muted)'}}>Очікуємо…</span>}
                  </div>
                  <div style={{fontSize:11,color:'var(--muted)',marginTop:1}}>
                    {p ? `⭐${room.stake}` : '─'}
                  </div>
                </div>
                {p?.is_you && (
                  <div style={{marginLeft:'auto',fontSize:11,color:'#FF9950',fontWeight:700}}>ТИ</div>
                )}
              </div>
            )
          })}
        </div>

        <div style={{fontSize:12,color:'var(--muted)',textAlign:'center',marginBottom:14,lineHeight:1.5}}>
          Кімната заповниться ботами якщо довго немає гравців
        </div>

        <button onClick={handleBack} style={{
          padding:'10px 28px',borderRadius:20,fontSize:14,fontWeight:700,
          background:'rgba(255,255,255,.07)',color:'var(--muted)',
          border:'1px solid rgba(255,255,255,.1)',cursor:'pointer',
        }}>
          ← Вийти (ставка не повертається)
        </button>
      </div>
    )
  }

  // ─── spinning / result screen ─────────────────────────────────────────────
  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'12px 12px 24px'}}>
      <div style={{width:'100%',display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
        <div style={{fontSize:16,fontWeight:800}}>
          {screen==='spinning'?'🎡 Крутиться...':'🎡 Результат'}
        </div>
        <div style={{fontSize:13,fontWeight:700,padding:'4px 11px',borderRadius:20,
          background:'rgba(255,215,0,.1)',border:'1px solid rgba(255,215,0,.3)'}}>
          ⭐ {balance??'…'}
        </div>
      </div>

      {/* wheel */}
      <div style={{position:'relative',marginBottom:14}}>
        <div style={{position:'absolute',top:0,left:'50%',transform:'translate(-50%,-100%)',zIndex:2}}>
          <svg width="22" height="26" viewBox="0 0 22 26">
            <defs>
              <linearGradient id="pg3" x1="0%"y1="0%"x2="0%"y2="100%">
                <stop offset="0%" stopColor="#FF9950"/>
                <stop offset="100%" stopColor="#FF3300"/>
              </linearGradient>
            </defs>
            <polygon points="11,26 0,0 22,0" fill="url(#pg3)"/>
          </svg>
        </div>
        <canvas ref={cvRef} width={SIZE} height={SIZE}
          style={{display:'block',borderRadius:'50%',
            boxShadow:'0 0 36px rgba(100,50,200,.3),0 8px 28px rgba(0,0,0,.5)'}}/>
        <canvas ref={ptRef} width={SIZE} height={SIZE}
          style={{position:'absolute',top:0,left:0,pointerEvents:'none',borderRadius:'50%'}}/>
      </div>

      {/* result card */}
      {screen==='result' && room && (
        <div style={{
          width:'100%',maxWidth:SIZE,borderRadius:16,padding:'16px 20px',marginBottom:14,textAlign:'center',
          background:room.winner_is_you
            ?'linear-gradient(135deg,rgba(76,175,72,.22),rgba(76,175,72,.05))'
            :'rgba(255,255,255,.04)',
          border:`1px solid ${room.winner_is_you?'rgba(76,175,72,.55)':'rgba(255,255,255,.1)'}`,
          boxShadow:room.winner_is_you?'0 0 32px rgba(76,175,72,.22)':'none',
          animation:'fadeIn .4s ease',
        }}>
          {room.winner_is_you ? (
            <>
              <div style={{fontSize:40,marginBottom:4}}>🎉</div>
              <div style={{fontSize:22,fontWeight:900,color:'#4CAF72'}}>Ти виграв!</div>
              <div style={{fontSize:18,marginTop:5,fontWeight:700}}>+⭐{room.payout}</div>
              <div style={{fontSize:12,color:'var(--muted)',marginTop:3}}>Баланс: ⭐{room.new_balance}</div>
            </>
          ) : (
            <>
              <div style={{fontSize:40,marginBottom:4}}>😔</div>
              <div style={{fontSize:18,fontWeight:800,color:'var(--muted)'}}>Не пощастило</div>
              <div style={{fontSize:13,color:'var(--muted)',marginTop:4}}>
                Переміг <strong style={{color:'var(--text)'}}>{room.winner_name}</strong> · ⭐{room.payout}
              </div>
              <div style={{fontSize:12,color:'var(--muted)',marginTop:2}}>Баланс: ⭐{room.new_balance}</div>
            </>
          )}
        </div>
      )}

      {screen==='result' && (
        <button className="btn btn-primary"
          onClick={handleBack}
          style={{width:'100%',maxWidth:SIZE,fontSize:15,fontWeight:800,padding:'13px 0'}}>
          Грати ще раз
        </button>
      )}

      <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}`}</style>
    </div>
  )
}
