import React, { useEffect, useState } from 'react'

const DEFAULT = { descText: '', descPos: 'auto', commentText: '', commentMode: 'ai' }

// Remembers the fixed description/comment across sessions (they're "fixed" boilerplate).
export function useFixed() {
  const [fixed, setFixed] = useState(() => {
    try { return { ...DEFAULT, ...(JSON.parse(localStorage.getItem('tm-fixed') || 'null') || {}) } }
    catch { return DEFAULT }
  })
  useEffect(() => { localStorage.setItem('tm-fixed', JSON.stringify(fixed)) }, [fixed])
  return [fixed, setFixed]
}

export function appendFixed(fd, fixed) {
  fd.append('fixed_desc_text', fixed.descText || '')
  fd.append('fixed_desc_position', fixed.descPos || 'auto')
  fd.append('fixed_comment_text', fixed.commentText || '')
  fd.append('fixed_comment_mode', fixed.commentMode || 'ai')
}

export default function FixedContent({ fixed, onChange }) {
  const set = (k, v) => onChange({ ...fixed, [k]: v })
  return (
    <>
      <div className="card">
        <div className="card-title"><span className="dot" />Fixed description <span className="muted" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 400 }}>— optional boilerplate added to every video</span></div>
        <textarea rows={4} placeholder={"e.g.\nFollow me:\nInstagram: @you\nWebsite: you.com"} value={fixed.descText} onChange={(e) => set('descText', e.target.value)} />
        <label className="field" style={{ marginTop: 12 }}>Position</label>
        <div className="segment">
          <button className={fixed.descPos === 'top' ? 'on' : ''} onClick={() => set('descPos', 'top')}>Top</button>
          <button className={fixed.descPos === 'bottom' ? 'on' : ''} onClick={() => set('descPos', 'bottom')}>Bottom</button>
          <button className={fixed.descPos === 'auto' ? 'on' : ''} onClick={() => set('descPos', 'auto')}>Auto-integrate</button>
        </div>
        <div className="hint">Auto places it after the content but keeps your hashtags on the last line — added verbatim, never rewritten.</div>
      </div>

      <div className="card">
        <div className="card-title"><span className="dot" />Fixed pinned comment <span className="muted" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 400 }}>— optional</span></div>
        <textarea rows={3} placeholder="e.g. 👉 Apply / join the community here: …" value={fixed.commentText} onChange={(e) => set('commentText', e.target.value)} />
        <label className="field" style={{ marginTop: 12 }}>Pinned comment</label>
        <div className="segment">
          <button className={fixed.commentMode === 'ai' ? 'on' : ''} onClick={() => set('commentMode', 'ai')}>Auto</button>
          <button className={fixed.commentMode === 'fixed' ? 'on' : ''} onClick={() => set('commentMode', 'fixed')}>Fixed only</button>
          <button className={fixed.commentMode === 'integrate' ? 'on' : ''} onClick={() => set('commentMode', 'integrate')}>Auto + fixed</button>
        </div>
        <div className="hint">Leave the box empty (or pick “Auto”) to skip the fixed comment entirely.</div>
      </div>
    </>
  )
}
