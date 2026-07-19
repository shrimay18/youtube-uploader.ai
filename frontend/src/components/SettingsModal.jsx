import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const KEYS = [
  { id: 'GEMINI_API_KEY', label: 'Gemini API key' },
  { id: 'YOUTUBE_API_KEY', label: 'YouTube Data API key' },
  { id: 'GROQ_API_KEY', label: 'Groq API key' },
  { id: 'ANTHROPIC_API_KEY', label: 'Anthropic key' },
]

export default function SettingsModal({ onClose }) {
  const [masked, setMasked] = useState({})
  const [vals, setVals] = useState({})
  const [flash, setFlash] = useState('')

  useEffect(() => { api.getKeys().then(setMasked).catch(() => {}) }, [])

  async function save() {
    const changed = Object.fromEntries(Object.entries(vals).filter(([, v]) => v && v.trim()))
    if (!Object.keys(changed).length) return setFlash('Nothing changed.')
    try { await api.saveKeys(changed); setFlash('Saved. Keys re-encrypted on this device.'); setVals({}); api.getKeys().then(setMasked) }
    catch (e) { setFlash('Error: ' + e.message) }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h2 className="hero-title" style={{ fontSize: 22, margin: 0 }}>API keys</h2>
          <button className="icon-btn" style={{ marginLeft: 'auto' }} onClick={onClose}>✕</button>
        </div>
        <p className="hero-sub" style={{ marginTop: 6 }}>Encrypted on this device. Leave a field blank to keep the current key.</p>
        {flash && <div className="flash info">{flash}</div>}
        {KEYS.map((k) => (
          <div key={k.id} style={{ marginBottom: 12 }}>
            <label className="field">{k.label} {masked[k.id] ? <span className="pill" style={{ marginLeft: 6 }}>{masked[k.id]}</span> : <span className="muted">not set</span>}</label>
            <input type="password" placeholder="enter a new key to replace" value={vals[k.id] || ''} onChange={(e) => setVals({ ...vals, [k.id]: e.target.value })} />
          </div>
        ))}
        <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
          <button className="btn btn-primary" onClick={save}>Save keys</button>
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}
