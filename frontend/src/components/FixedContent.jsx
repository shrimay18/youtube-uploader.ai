import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const DEFAULT = { descText: '', descPos: 'auto', commentText: '', commentMode: 'ai' }

// snake_case (server / encrypted vault) <-> camelCase (UI)
const fromServer = (d) => ({
  descText: d?.desc_text || '', descPos: d?.desc_position || 'auto',
  commentText: d?.comment_text || '', commentMode: d?.comment_mode || 'ai',
})
const toServer = (f) => ({
  desc_text: f.descText || '', desc_position: f.descPos || 'auto',
  comment_text: f.commentText || '', comment_mode: f.commentMode || 'ai',
})

// Fixed boilerplate is set ONCE and applied to every upload. It lives encrypted on
// this device (vault key) like your API keys, so it survives across sessions,
// browsers and devices — you never retype it. localStorage is just an instant cache.
export function useFixed() {
  const [fixed, setFixed] = useState(() => {
    try { return { ...DEFAULT, ...(JSON.parse(localStorage.getItem('tm-fixed') || 'null') || {}) } }
    catch { return DEFAULT }
  })
  const [saved, setSaved] = useState('idle')  // 'idle' | 'saving' | 'saved'
  const loaded = useRef(false)
  const timer = useRef(null)

  useEffect(() => {   // pull the authoritative value from the server once
    let alive = true
    api.getFixed()
      .then((d) => { if (alive) setFixed({ ...DEFAULT, ...fromServer(d) }) })
      .catch(() => {})   // locked / offline -> keep the cached value
      .finally(() => { loaded.current = true })
    return () => { alive = false }
  }, [])

  useEffect(() => {   // cache instantly, persist (debounced) as the source of truth
    try { localStorage.setItem('tm-fixed', JSON.stringify(fixed)) } catch {}
    if (!loaded.current) return   // don't clobber the server before the first load lands
    setSaved('saving')
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      api.saveFixed(toServer(fixed)).then(() => setSaved('saved')).catch(() => setSaved('idle'))
    }, 600)
    return () => clearTimeout(timer.current)
  }, [fixed])

  return [fixed, setFixed, saved]
}

export function appendFixed(fd, fixed) {
  fd.append('fixed_desc_text', fixed.descText || '')
  fd.append('fixed_desc_position', fixed.descPos || 'auto')
  fd.append('fixed_comment_text', fixed.commentText || '')
  fd.append('fixed_comment_mode', fixed.commentMode || 'ai')
}

function SavedTag({ saved }) {
  if (saved === 'saving') return <span className="fx-saved saving">Saving…</span>
  if (saved === 'saved') return <span className="fx-saved ok">Saved · reused for every upload</span>
  return null
}

export default function FixedContent({ fixed, onChange, saved }) {
  const set = (k, v) => onChange({ ...fixed, [k]: v })
  return (
    <>
      <div className="card">
        <div className="card-title"><span className="dot" />Fixed description <span className="muted" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 400 }}>· set once, added to every video</span><SavedTag saved={saved} /></div>
        <textarea rows={4} placeholder={"e.g.\nFollow me:\nInstagram: @you\nWebsite: you.com"} value={fixed.descText} onChange={(e) => set('descText', e.target.value)} />
        <label className="field" style={{ marginTop: 12 }}>Position</label>
        <div className="segment">
          <button className={fixed.descPos === 'top' ? 'on' : ''} onClick={() => set('descPos', 'top')}>Top</button>
          <button className={fixed.descPos === 'bottom' ? 'on' : ''} onClick={() => set('descPos', 'bottom')}>Bottom</button>
          <button className={fixed.descPos === 'auto' ? 'on' : ''} onClick={() => set('descPos', 'auto')}>Auto-integrate</button>
        </div>
        <div className="hint">Auto places it after the content but keeps your hashtags on the last line. Added verbatim, never rewritten. Saved automatically; clear the box to stop adding it.</div>
      </div>

      <div className="card">
        <div className="card-title"><span className="dot" />Fixed pinned comment <span className="muted" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 400 }}>· set once, pinned on every video</span><SavedTag saved={saved} /></div>
        <textarea rows={3} placeholder="e.g. 👉 Apply / join the community here: …" value={fixed.commentText} onChange={(e) => set('commentText', e.target.value)} />
        <label className="field" style={{ marginTop: 12 }}>Pinned comment</label>
        <div className="segment">
          <button className={fixed.commentMode === 'ai' ? 'on' : ''} onClick={() => set('commentMode', 'ai')}>Auto</button>
          <button className={fixed.commentMode === 'fixed' ? 'on' : ''} onClick={() => set('commentMode', 'fixed')}>Fixed only</button>
          <button className={fixed.commentMode === 'integrate' ? 'on' : ''} onClick={() => set('commentMode', 'integrate')}>Auto + fixed</button>
        </div>
        <div className="hint">Saved automatically and reused for every upload. Clear the box (or pick “Auto”) to stop adding a fixed comment.</div>
      </div>
    </>
  )
}
