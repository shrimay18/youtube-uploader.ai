import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { KEY_GUIDES, KeyField } from './KeyGuide.jsx'

// Shown right after a first sign-in when the required keys aren't set yet.
// Same step-by-step guides as signup, so Google users get a smooth setup too.
export default function KeysOnboarding({ onDone }) {
  const [masked, setMasked] = useState({})
  const [vals, setVals] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { api.getKeys().then(setMasked).catch(() => {}) }, [])

  const has = (id) => !!masked[id] || !!(vals[id] && vals[id].trim())
  const ready = has('GEMINI_API_KEY') && has('YOUTUBE_API_KEY')

  async function save() {
    setError('')
    const changed = Object.fromEntries(Object.entries(vals).filter(([, v]) => v && v.trim()))
    if (Object.keys(changed).length) {
      setBusy(true)
      try { await api.saveKeys(changed) }
      catch (e) { setError(e.message); setBusy(false); return }
    }
    onDone()
  }

  return (
    <div className="modal-back">
      <div className="modal onboard-modal" onClick={(e) => e.stopPropagation()}>
        <div className="onboard-head">
          <div className="onboard-badge">Welcome 👋</div>
          <h2 className="hero-title" style={{ fontSize: 24, margin: '10px 0 6px' }}>Let’s add your keys</h2>
          <p className="hero-sub" style={{ margin: 0 }}>
            youtube_manager.ai runs on <b>your own</b> API keys — they’re encrypted on this
            device and never sent to us. You only need the two free ones to begin. Not sure
            where to find a key? Hit <b>“How do I get this?”</b> next to it for exact steps.
          </p>
        </div>

        {error && <div className="flash bad">{error}</div>}

        <div className="onboard-keys">
          {KEY_GUIDES.map((g) => (
            <KeyField key={g.id} guide={g} detected={!!masked[g.id]}
              value={vals[g.id]} onChange={(v) => setVals({ ...vals, [g.id]: v })} />
          ))}
        </div>

        <div className="onboard-actions">
          <button className="btn btn-primary btn-lg" disabled={!ready || busy} onClick={save}>
            {busy ? 'Saving…' : ready ? 'Save & start' : 'Add Gemini + YouTube keys to continue'}
          </button>
          <button className="btn btn-ghost" disabled={busy} onClick={onDone}>I’ll do this later</button>
        </div>
        <p className="muted" style={{ textAlign: 'center', marginTop: 12 }}>
          🔒 Keys are encrypted locally with your account. You can edit them anytime from the account menu.
        </p>
      </div>
    </div>
  )
}
