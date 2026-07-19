import React from 'react'

export default function Landing({ accountExists, onGetStarted, onSignIn }) {
  const cta = accountExists ? 'Open the studio' : 'Get started'
  return (
    <div className="landing">
      <section className="hero2">
        <div className="hero2-copy">
          <div className="eyebrow"><span className="tick" /> Local &amp; private · your keys never leave your device</div>
          <h1>Publish smarter,<br />not harder.</h1>
          <p className="lede">
            <b>youtube_manager.ai</b> turns a raw video into a fully SEO-optimized, upload-ready
            YouTube post — title, description, tags, thumbnail — by studying what actually ranks
            for your topic. One video or a whole folder, reviewed your way, then published or
            scheduled.
          </p>
          <div className="hero-cta">
            <button className="btn btn-primary btn-lg" onClick={onGetStarted}>{cta}</button>
            {!accountExists && <button className="btn btn-ghost btn-lg" onClick={onSignIn}>I have an account</button>}
          </div>
          <div className="trust">No subscription · No cloud · Bring your own free API keys</div>
        </div>

        <div className="hero2-visual" aria-hidden="true">
          <div className="glow" />
          <div className="mock">
            <div className="mock-top"><span className="mock-dot" /><span className="mock-dot" /><span className="mock-dot" /><span className="mock-name">▶ Delta Education · Short</span></div>
            <div className="mock-label">Titles · scored 0–100</div>
            <div className="mock-opt on"><span className="score good">95</span><span>Scaler School of Technology Hostel &amp; Food Tour (2026)</span></div>
            <div className="mock-opt"><span className="score good">88</span><span>Inside the SST Hostel — Honest Food Review</span></div>
            <div className="mock-opt"><span className="score ok">67</span><span>Scaler School Food Review</span></div>
            <div className="mock-tags">
              <span className="tag-chip">scaler school of technology</span>
              <span className="tag-chip">nset</span>
              <span className="tag-chip">scaler hostel tour</span>
              <span className="tag-chip">sst placements</span>
            </div>
            <div className="mock-actions"><span className="mock-btn">Schedule</span><span className="mock-btn ghost">Publish</span></div>
          </div>
        </div>
      </section>

      <section className="flow">
        <div className="flow-step"><span className="flow-n">01</span><div><b>Add a video</b><p>Drive link, a folder for bulk, or a file.</p></div></div>
        <div className="flow-arrow">→</div>
        <div className="flow-step"><span className="flow-n">02</span><div><b>AI does the work</b><p>Transcript → ranking research → scored metadata + thumbnail.</p></div></div>
        <div className="flow-arrow">→</div>
        <div className="flow-step"><span className="flow-n">03</span><div><b>Review &amp; publish</b><p>Tweak, then publish, keep private, or schedule.</p></div></div>
      </section>

      <section className="privacy-band">
        <div className="lock-badge">🔐</div>
        <h2>Your keys. Your machine. Nobody else’s business.</h2>
        <p>
          There’s no cloud and no accounts server. You bring your own free API keys — they’re
          <b> encrypted on your device with your password</b> and never sent to us or anyone. Every
          step, from transcription to upload, happens on your computer.
        </p>
        <button className="btn btn-primary btn-lg" onClick={onGetStarted} style={{ marginTop: 4 }}>{cta}</button>
      </section>

      <footer className="landing-foot">youtube_manager.ai — built for creators who’d rather create.</footer>
    </div>
  )
}
