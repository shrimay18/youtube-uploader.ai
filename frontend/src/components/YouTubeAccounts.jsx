import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const VOICE_FIELDS = [
  { id: 'niche', label: 'Niche / topic', ph: 'e.g. edtech reviews, career advice for students' },
  { id: 'audience', label: 'Audience', ph: 'e.g. Indian college students & job seekers' },
  { id: 'tone', label: 'Tone', ph: 'e.g. honest, energetic, no-fluff' },
  { id: 'default_cta', label: 'Default call-to-action', ph: 'e.g. Subscribe for weekly deep-dives' },
]

function Avatar({ a }) {
  if (a.thumbnail) return <img className="yt-avatar" src={a.thumbnail} alt="" referrerPolicy="no-referrer" />
  return <div className="yt-avatar fallback">{(a.title || '?').slice(0, 1).toUpperCase()}</div>
}

export default function YouTubeAccounts({ onClose, onChanged }) {
  const [accounts, setAccounts] = useState(null)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState('')
  const [showSteps, setShowSteps] = useState(false)
  const [editing, setEditing] = useState(null)   // account id whose voice is open

  const load = () => api.ytAccounts().then((a) => setAccounts(a)).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  async function connect() {
    setError(''); setConnecting(true)
    try {
      await api.ytConnect()   // blocks while the browser OAuth completes
      await load()
      onChanged?.()
    } catch (e) { setError(e.message) }
    setConnecting(false)
  }

  async function remove(a) {
    if (!confirm(`Disconnect “${a.title}”? It stays on YouTube — this only removes it from youtube_manager.`)) return
    await api.ytRemove(a.id).catch(() => {})
    await load(); onChanged?.()
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal yt-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'flex-start' }}>
          <div>
            <h2 className="hero-title" style={{ fontSize: 22, margin: 0 }}>YouTube accounts</h2>
            <p className="hero-sub" style={{ margin: '6px 0 0' }}>Connect as many channels as you like, then post to several at once.</p>
          </div>
          <button className="icon-btn" style={{ marginLeft: 'auto' }} onClick={onClose} title="Close">✕</button>
        </div>

        {error && <div className="flash bad" style={{ marginTop: 14 }}>{error}</div>}

        <div className="yt-list">
          {accounts === null && <div className="stage-line"><div className="spinner" /><span>Loading…</span></div>}
          {accounts?.length === 0 && (
            <div className="yt-empty">No channels connected yet. Connect your first one below 👇</div>
          )}
          {accounts?.map((a) => (
            <div key={a.id} className="yt-row">
              <div className="yt-row-main">
                <Avatar a={a} />
                <div className="yt-meta">
                  <b>{a.title}</b>
                  <span>{a.handle || 'YouTube channel'} · {a.profile_ok
                    ? <span className="ok-text">voice set</span>
                    : <span className="warn-text">set its voice</span>}</span>
                </div>
                <div className="yt-row-actions">
                  <button className="btn btn-ghost sm" onClick={() => setEditing(editing === a.id ? null : a.id)}>
                    {editing === a.id ? 'Close' : 'Voice'}
                  </button>
                  <button className="btn btn-ghost sm danger" onClick={() => remove(a)}>Remove</button>
                </div>
              </div>
              {editing === a.id && <VoiceEditor account={a} onSaved={() => { load(); setEditing(null) }} />}
            </div>
          ))}
        </div>

        <button className="btn btn-primary btn-block btn-lg" style={{ marginTop: 16 }} disabled={connecting} onClick={connect}>
          {connecting ? 'Complete sign-in in the browser…' : '＋ Connect a YouTube account'}
        </button>

        <button className="how-btn" style={{ marginLeft: 0, marginTop: 12 }} onClick={() => setShowSteps((s) => !s)}>
          {showSteps ? 'Hide steps' : 'How does connecting work?'}
        </button>
        {showSteps && (
          <div className="how-panel" style={{ marginLeft: 0 }}>
            <ol className="how-steps">
              <li>Click <b>Connect a YouTube account</b> — a Google window opens.</li>
              <li>Pick the Google account (or <b>Brand Account</b>) that owns the channel you want to add.</li>
              <li>Approve the YouTube permission so youtube_manager can upload on your behalf.</li>
              <li>You’ll bounce back here and the channel appears in the list.</li>
              <li>Repeat to add more channels. Each one is stored encrypted on this device.</li>
            </ol>
            <div className="how-note">💡 To add a second channel under the same Google login, the picker lets you choose a different Brand Account. Use “Use another account” for a different Google login entirely.</div>
          </div>
        )}
      </div>
    </div>
  )
}

function VoiceEditor({ account, onSaved }) {
  const [vals, setVals] = useState(() => ({ ...(account.profile || {}) }))
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  async function save() {
    setBusy(true); setMsg('')
    try {
      await api.ytSetProfile(account.id, {
        niche: vals.niche || '', audience: vals.audience || '',
        tone: vals.tone || '', default_cta: vals.default_cta || '',
      })
      onSaved()
    } catch (e) { setMsg(e.message); setBusy(false) }
  }

  return (
    <div className="yt-voice">
      <div className="hint" style={{ margin: '0 0 10px' }}>
        This shapes the titles &amp; descriptions generated for this channel’s voice.
      </div>
      {msg && <div className="flash bad">{msg}</div>}
      {VOICE_FIELDS.map((f) => (
        <div key={f.id} style={{ marginBottom: 10 }}>
          <label className="field">{f.label}</label>
          <input type="text" placeholder={f.ph} value={vals[f.id] || ''}
            onChange={(e) => setVals({ ...vals, [f.id]: e.target.value })} />
        </div>
      ))}
      <button className="btn btn-primary sm" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save voice'}</button>
    </div>
  )
}
