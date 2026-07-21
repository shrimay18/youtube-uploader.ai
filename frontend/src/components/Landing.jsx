import React, { useEffect, useRef, useState } from 'react'

// Reel cards for the marquee — each plays a (blurred) real clip and reveals a
// creator-milestone caption on hover. Clips are small public CC sample videos.
const TV = 'https://test-videos.co.uk/vids/'
const CL = 'https://res.cloudinary.com/demo/video/upload/'
const REELS = [
  { g: 'linear-gradient(135deg,#ff2246,#ff8a3d)', d: '0:42', e: '🎉', t: 'Hit your first 1M views', v: CL + 'dog.mp4' },
  { g: 'linear-gradient(135deg,#6b5bff,#37c6ff)', d: '8:10', e: '🚀', t: 'This one went viral', v: TV + 'jellyfish/mp4/h264/360/Jellyfish_360_10s_1MB.mp4' },
  { g: 'linear-gradient(135deg,#12b981,#37c6ff)', d: '12:04', e: '📈', t: '+340% views this week', v: CL + 'elephants.mp4' },
  { g: 'linear-gradient(135deg,#ff2246,#6b5bff)', d: '3:28', e: '🔥', t: '#1 Trending in Education', v: TV + 'bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4' },
  { g: 'linear-gradient(135deg,#ffd23f,#ff2246)', d: '6:55', e: '💰', t: 'Channel just monetized', v: CL + 'sea_turtle.mp4' },
  { g: 'linear-gradient(135deg,#37c6ff,#12b981)', d: '0:59', e: '🏆', t: 'Crossed 100K subs', v: TV + 'sintel/mp4/h264/360/Sintel_360_10s_1MB.mp4' },
]
const HERO_VID = TV + 'bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_2MB.mp4'
const CONFETTI = ['#ff2246', '#ffd23f', '#12b981', '#6b5bff', '#37c6ff', '#ff8a3d']

const SunIcon = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" /></svg>)
const MoonIcon = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>)

// "Creator studio" landing (design 3): the hero is a living dashboard.
export default function Landing({ accountExists, onGetStarted, onSignIn, onNav, onFeedback, theme, onToggleTheme }) {
  const root = useRef(null)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const el = root.current
    if (!el) return
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const observers = []
    const cleanups = []

    // scroll reveals
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target) }
    }), { threshold: 0.14 })
    el.querySelectorAll('.rv').forEach((n) => io.observe(n))
    observers.push(io)

    // real clips: force muted autoplay, and pause when scrolled off-screen (saves CPU/data)
    const vids = el.querySelectorAll('video')
    const kick = (v) => { const p = v.play(); if (p && p.catch) p.catch(() => {}) }
    vids.forEach((v) => { v.muted = true; kick(v) })
    const vo = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) kick(e.target); else e.target.pause()
    }), { threshold: 0 })
    vids.forEach((v) => vo.observe(v)); observers.push(vo)

    // draw the hand-drawn marker circle when the hero shows
    const hero = el.querySelector('.hero')
    if (hero) {
      const ho = new IntersectionObserver((es, ob) => es.forEach((e) => {
        if (e.isIntersecting) { hero.classList.add('lit'); ob.disconnect() }
      }), { threshold: 0.3 })
      ho.observe(hero); observers.push(ho)
    }

    // draw the graph + tick the view counter when the dashboard scrolls in
    const dash = el.querySelector('.dash')
    const count = el.querySelector('.count')
    if (dash) {
      const ease = (t) => 1 - Math.pow(1 - t, 3)
      const do_ = new IntersectionObserver((es, ob) => es.forEach((e) => {
        if (!e.isIntersecting) return
        ob.disconnect(); dash.classList.add('lit')
        if (count) {
          const target = 48213, dur = 1600; let t0 = null
          const step = (ts) => { if (!t0) t0 = ts; const p = Math.min((ts - t0) / dur, 1); count.firstChild.textContent = Math.floor(ease(p) * target).toLocaleString(); if (p < 1) requestAnimationFrame(step) }
          requestAnimationFrame(step)
        }
      }), { threshold: 0.4 })
      do_.observe(dash); observers.push(do_)

      // 3D tilt
      if (!reduce) {
        const move = (ev) => { const r = dash.getBoundingClientRect(); dash.style.setProperty('--ry', ((ev.clientX - r.left) / r.width - 0.5) * 8 + 'deg'); dash.style.setProperty('--rx', (-((ev.clientY - r.top) / r.height - 0.5)) * 8 + 'deg') }
        const leave = () => { dash.style.setProperty('--ry', '0deg'); dash.style.setProperty('--rx', '0deg') }
        dash.addEventListener('pointermove', move); dash.addEventListener('pointerleave', leave)
        cleanups.push(() => { dash.removeEventListener('pointermove', move); dash.removeEventListener('pointerleave', leave) })
      }
    }

    return () => { observers.forEach((o) => o.disconnect()); cleanups.forEach((fn) => fn()) }
  }, [])

  // confetti burst at a point, then run cb (so the delight is seen before navigating)
  function celebrate(e, cb) {
    e?.preventDefault?.()
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!reduce && e?.currentTarget) {
      const r = e.currentTarget.getBoundingClientRect()
      const x = r.left + r.width / 2, y = r.top + r.height / 2
      for (let i = 0; i < 34; i++) {
        const d = document.createElement('div')
        const s = 6 + Math.random() * 7
        d.style.cssText = `position:fixed;left:${x}px;top:${y}px;width:${s}px;height:${s}px;background:${CONFETTI[i % CONFETTI.length]};border-radius:2px;z-index:9999;pointer-events:none;will-change:transform,opacity`
        document.body.appendChild(d)
        const ang = Math.random() * 6.28, vel = 120 + Math.random() * 220
        d.animate([
          { transform: 'translate(0,0) rotate(0)', opacity: 1 },
          { transform: `translate(${Math.cos(ang) * vel}px,${Math.sin(ang) * vel - 120 + 260}px) rotate(${Math.random() * 720 - 360}deg)`, opacity: 0 },
        ], { duration: 900 + Math.random() * 500, easing: 'cubic-bezier(.2,.6,.3,1)' }).onfinish = () => d.remove()
      }
      setTimeout(() => cb?.(), 480)
    } else { cb?.() }
  }

  const start = (e) => celebrate(e, onGetStarted)
  const scrollTo = (e, id) => { e.preventDefault(); root.current?.querySelector('#' + id)?.scrollIntoView({ behavior: 'smooth' }) }
  const top = (e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  return (
    <div className="mkt" ref={root}>
      <header className="nav">
        <div className="nav-inner">
          <a className="logo" href="#top" onClick={top}>
            <span className="m"><svg viewBox="0 0 24 24" fill="#fff"><path d="M4 4l16 8-16 8z" /></svg></span>
            <span className="name">youtube_manager<b>.ai</b></span>
          </a>
          <div className="nav-actions">
            <button className="nav-theme" onClick={onToggleTheme} title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'} aria-label="Toggle theme">{theme === 'dark' ? <SunIcon /> : <MoonIcon />}</button>
            <button className="fb-btn" onClick={onFeedback}>Feedback</button>
            <a className="lnk" href="#login" onClick={(e) => { e.preventDefault(); onSignIn?.() }}>Log in</a>
          </div>
          <button className={'nav-burger' + (menuOpen ? ' open' : '')} onClick={() => setMenuOpen((o) => !o)} aria-label="Menu" aria-expanded={menuOpen}>
            <span /><span /><span />
          </button>
        </div>
        {menuOpen && (
          <>
            <div className="nav-scrim" onClick={() => setMenuOpen(false)} />
            <div className="nav-sheet">
              <button onClick={() => { setMenuOpen(false); onSignIn?.() }}>Log in</button>
              <button onClick={onToggleTheme}>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</button>
              <button onClick={() => { setMenuOpen(false); onFeedback?.() }}>Feedback</button>
            </div>
          </>
        )}
      </header>

      <main className="wrap" id="top">
        <section className="hero" id="hero">
          <div className="hgrid">
            <div className="rv">
              <h1>Go from upload<br />to <span className="mark">trending
                <svg viewBox="0 0 300 90" preserveAspectRatio="none"><path d="M18 62 C 60 12, 250 6, 286 40 C 300 66, 210 88, 120 84 C 44 80, 10 66, 30 44" pathLength="1" /></svg>
              </span>.</h1>
              <p className="lede">Drop a video and youtube_manager.ai writes the <span className="hl">title, tags, chapters &amp; thumbnail</span> that actually rank, then publishes to every channel you own. From your desk or your phone.</p>
              <div className="cta-row">
                <button className="btn btn-red" onClick={start}>{accountExists ? 'Open studio' : 'Start creating'}</button>
                <a className="btn btn-ink" href="#how" onClick={(e) => scrollTo(e, 'how')}>See it work</a>
              </div>
              <div className="trust">
                <div className="stack">
                  <i style={{ backgroundImage: "url('/assets/shrimay.jpg')" }} />
                  <i style={{ backgroundImage: "url('/assets/delta.jpg')" }} />
                  <i style={{ background: 'linear-gradient(135deg,#6b5bff,#37c6ff)' }} />
                </div>
                Built for creators · your keys never leave your device
              </div>
            </div>

            <div className="dash rv">
              <span className="float f1" aria-hidden="true">🔥</span>
              <span className="float f2" aria-hidden="true">✨</span>
              <div className="player">
                <video className="pvid" src={HERO_VID} muted loop autoPlay playsInline preload="auto" />
                <div className="sheen" />
                <span className="live"><b /> AUTO-EDIT</span>
                <div className="play" />
                <div className="scrub"><b /><i /></div>
              </div>
              <div className="meta">
                <p className="vt">I Tried Every Hostel in Manali 🏔️ (Brutally Honest)</p>
                <div className="stats">
                  <div><div className="count"><span>0</span><small>+312% vs last week</small></div></div>
                  <div className="graph">
                    <svg viewBox="0 0 200 56" preserveAspectRatio="none">
                      <defs><linearGradient id="mk3gg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#12b981" stopOpacity=".45" /><stop offset="1" stopColor="#12b981" stopOpacity="0" /></linearGradient></defs>
                      <path className="area" d="M0 48 L18 44 L40 46 L62 34 L86 36 L112 24 L140 26 L168 12 L200 6 L200 56 L0 56 Z" pathLength="1" />
                      <path className="line" d="M0 48 L18 44 L40 46 L62 34 L86 36 L112 24 L140 26 L168 12 L200 6" pathLength="1" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="strip">
            <div className="track">
              {[...Array(2)].flatMap((_, r) => REELS.map((m, i) => (
                <div key={r + '-' + i} className="thumb" style={{ '--g': m.g }}>
                  <video className="rvid" src={m.v} muted loop autoPlay playsInline preload="auto" />
                  <div className="tint" />
                  <div className="ply" />
                  <span className="tag">{m.d}</span>
                  <div className="cap"><b>{m.e}</b><span>{m.t}</span></div>
                </div>
              )))}
            </div>
          </div>
        </section>

        <section id="how">
          <span className="kick">the whole workflow</span>
          <h2 className="rv">Three steps. Zero busywork.</h2>
          <div className="steps">
            <div className="step rv"><div className="tag">STEP 01</div><h3>Drop your video</h3><p>Paste a Drive link or upload a file. Any length, from any device.</p><div className="bar" /></div>
            <div className="step rv"><div className="tag">STEP 02</div><h3>We optimize it</h3><p>Full transcription → SEO title, description, tags, chapters &amp; a thumbnail tuned to what ranks.</p><div className="bar" /></div>
            <div className="step rv"><div className="tag">STEP 03</div><h3>Publish everywhere</h3><p>Send it to every channel at once. Review each or push live in one tap.</p><div className="bar" /></div>
          </div>
        </section>

        <section>
          <span className="kick">the toolkit</span>
          <h2 className="rv">Everything a channel needs, automated.</h2>
          <div className="feat">
            <div className="card big rv"><div className="ic">🎯</div><h3>Ranks, not filler</h3><p>Titles &amp; tags are reverse-engineered from what already ranks for your topic, then scored for SEO before you post.</p></div>
            <div className="card rv"><div className="ic">📡</div><h3>Every channel</h3><p>Connect unlimited YouTube channels and push one video to all of them at once, each in its own voice.</p></div>
            <div className="card rv"><div className="ic">🗓️</div><h3>Schedule &amp; stagger</h3><p>Batch an entire Drive folder and auto-space the uploads over days, keeping a steady posting rhythm.</p></div>
            <div className="card rv"><div className="ic">🔐</div><h3>Yours only</h3><p>Your keys, tokens and videos are encrypted on your own device and never reach our servers.</p></div>
            <div className="card rv"><div className="ic">🧩</div><h3>Your own API keys</h3><p>Plug in your own Gemini, Groq, OpenAI or Claude keys. They rotate automatically, so you only pay your own AI bill.</p></div>
          </div>
        </section>

        <section id="channels">
          <span className="kick">multi-channel</span>
          <h2 className="rv">Run every channel like it’s one.</h2>
          <p className="sub2 rv" style={{ marginBottom: 6 }}>Drop one video and watch it publish to every channel at once.</p>
          <div className="broadcast rv">
            <div className="src">
              <div className="src-thumb"><span className="ply2" /></div>
              <div className="src-meta"><b>Your video</b><span>ready to publish</span></div>
            </div>
            <div className="wires" aria-hidden="true">
              <svg viewBox="0 0 92 264" preserveAspectRatio="none">
                <defs><linearGradient id="wg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#ff2246" /><stop offset="1" stopColor="#12b981" /></linearGradient></defs>
                {/* one line to each channel — top, center, bottom */}
                <path className="base" d="M2 132 C46 132 46 34 90 34" />
                <path className="base" d="M2 132 C46 132 46 132 90 132" />
                <path className="base" d="M2 132 C46 132 46 230 90 230" />
                <path className="flow f1" d="M2 132 C46 132 46 34 90 34" pathLength="1" />
                <path className="flow f2" d="M2 132 C46 132 46 132 90 132" pathLength="1" />
                <path className="flow f3" d="M2 132 C46 132 46 230 90 230" pathLength="1" />
                {/* glowing packets travelling out to each channel */}
                <circle className="orb" r="3.4"><animateMotion path="M2 132 C46 132 46 34 90 34" dur="2.6s" repeatCount="indefinite" /></circle>
                <circle className="orb" r="3.4"><animateMotion path="M2 132 C46 132 46 132 90 132" dur="2.6s" begin="-0.55s" repeatCount="indefinite" /></circle>
                <circle className="orb" r="3.4"><animateMotion path="M2 132 C46 132 46 230 90 230" dur="2.6s" begin="-1.1s" repeatCount="indefinite" /></circle>
                {/* pulsing source + destination pins */}
                <circle className="src-pin" cx="2" cy="132" r="4" />
                <circle className="pin" cx="90" cy="34" r="3.2" />
                <circle className="pin" cx="90" cy="132" r="3.2" />
                <circle className="pin" cx="90" cy="230" r="3.2" />
              </svg>
            </div>
            <div className="dests">
              <div className="dchan"><img src="/assets/shrimay.jpg" alt="" /><div className="who"><b>Shrimay Somani</b><span>@shrimay_somani</span></div><span className="st">live</span><div className="up"><i /></div></div>
              <div className="dchan"><img src="/assets/delta.jpg" alt="" /><div className="who"><b>Delta Education</b><span>@DeltaEducation-18</span></div><span className="st">live</span><div className="up"><i /></div></div>
              <div className="dchan"><span className="fb" style={{ background: 'linear-gradient(135deg,#37c6ff,#6b5bff)' }}>C</span><div className="who"><b>Clips &amp; Shorts</b><span>@yourclips</span></div><span className="st">live</span><div className="up"><i /></div></div>
            </div>
          </div>

          <div className="priv rv">
            <span className="priv-aura" aria-hidden="true" />
            <div className="priv-head">
              <div className="lk">
                <svg className="lock" viewBox="0 0 48 52" fill="none" aria-hidden="true">
                  <path className="shackle" d="M14 24 v-7 a10 10 0 0 1 20 0 v7" stroke="currentColor" strokeWidth="4.5" strokeLinecap="round" />
                  <rect className="body" x="7" y="23" width="34" height="26" rx="7" fill="currentColor" />
                  <circle cx="24" cy="34" r="3.4" fill="#0e0d16" /><rect x="22.4" y="34" width="3.2" height="9" rx="1.6" fill="#0e0d16" />
                </svg>
              </div>
              <h3>What&rsquo;s yours stays yours.</h3>
            </div>
            <p>Encrypted right here with a key only you hold. Nothing ever touches our servers, so no one, not even us, can read a thing.</p>
          </div>
        </section>

        <section id="start">
          <div className="final rv">
            <div className="final-bg" aria-hidden="true">
              <div className="final-reel">
                {[...REELS, ...REELS].map((m, i) => (
                  <video key={i} src={m.v} muted loop autoPlay playsInline preload="none" />
                ))}
              </div>
              <div className="final-aurora" />
            </div>
            <span className="fsym s1" aria-hidden="true">🎬</span>
            <span className="fsym s2" aria-hidden="true">📈</span>
            <span className="fsym s3" aria-hidden="true">🔥</span>
            <span className="fsym s4" aria-hidden="true">✨</span>
            <span className="fsym s5" aria-hidden="true">🚀</span>
            <span className="fsym s6" aria-hidden="true">▶</span>
            <div className="final-inner">
              <span className="final-kick">your move</span>
              <div className="final-head"><span className="trace" aria-hidden="true" /><h2>Make the algorithm work for you.</h2></div>
              <p className="final-sub">One upload to every channel. The title, tags &amp; thumbnail that rank, done while you sleep.</p>
              <button className="cta-shiny" onClick={start}><span className="sweep" />{accountExists ? '🎬 Open the studio' : '🎬 Start creating'}</button>
            </div>
          </div>
        </section>
      </main>

      <footer>
        © {new Date().getFullYear()} youtube_manager.ai · made for creators
        <div className="links">
          <a onClick={() => onNav?.('privacy')}>Privacy</a>
          <a onClick={() => onNav?.('terms')}>Terms</a>
          <a onClick={onGetStarted}>Get started</a>
        </div>
      </footer>
    </div>
  )
}
