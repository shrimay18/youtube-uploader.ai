import React, { useState } from 'react'
import { api } from '../api.js'
import FixedContent, { useFixed } from './FixedContent.jsx'

export default function BulkSetup({ accounts = [], onManageAccounts, onStart }) {
  const [selected, setSelected] = useState([])
  const [input, setInput] = useState('')
  const [pub, setPub] = useState('review') // review | private | schedule | now
  const [schedAt, setSchedAt] = useState('')
  const [stagger, setStagger] = useState(60)
  const [fixed, setFixed, fixedSaved] = useFixed()
  const [resolving, setResolving] = useState(false)
  const [error, setError] = useState('')

  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])
  const allSelected = accounts.length > 0 && selected.length === accounts.length
  const toggleAll = () => setSelected(allSelected ? [] : accounts.map((a) => a.id))
  const voiceId = selected[0]
  const voice = accounts.find((a) => a.id === voiceId)
  const canGo = selected.length && input.trim() && !resolving && (pub !== 'schedule' || schedAt)

  async function start() {
    setError('')
    setResolving(true)
    try {
      const { videos } = await api.resolveDrive(input.trim())
      if (!videos?.length) throw new Error('No videos found in that input.')
      onStart(videos, {
        accountIds: selected, voiceId,
        autoPublish: pub !== 'review',
        publishMode: pub === 'review' ? 'private' : pub,
        schedAt, stagger: Number(stagger) || 0, fixed,
      })
    } catch (e) {
      setError(e.message || 'Could not resolve links')
      setResolving(false)
    }
  }

  return (
    <div>
      <h1 className="hero-title">Bulk upload</h1>
      <p className="hero-sub">Paste a Drive <b>folder</b> link (all videos inside) or multiple file links, one per line. Each becomes its own tab, processed in parallel.</p>

      {error && <div className="flash bad">{error}</div>}

      <div className="card">
        <div className="card-title"><span className="dot" />Publish to <span className="muted" style={{ textTransform: 'none', letterSpacing: 0, marginLeft: 6, fontWeight: 400 }}>· pick one or more channels</span></div>
        {accounts.length === 0 ? (
          <div className="empty-cta">
            <div>No YouTube channels connected yet.</div>
            <button className="btn btn-primary" onClick={onManageAccounts}>＋ Connect a YouTube account</button>
          </div>
        ) : (
          <>
            <div className="chips">
              {accounts.length > 1 && (
                <div className={'chip selectall' + (allSelected ? ' on' : '')} onClick={toggleAll}>
                  <span className="chk">{allSelected ? '✓' : ''}</span>
                  <div className="avatar all">★</div>
                  <div className="meta"><b>All channels</b><span>{allSelected ? 'all selected' : `${accounts.length} channels`}</span></div>
                </div>
              )}
              {accounts.map((a) => (
                <div key={a.id} className={'chip' + (selected.includes(a.id) ? ' on' : '')} onClick={() => toggle(a.id)}>
                  <span className="chk">{selected.includes(a.id) ? '✓' : ''}</span>
                  {a.thumbnail ? <img className="avatar img" src={a.thumbnail} alt="" referrerPolicy="no-referrer" />
                    : <div className="avatar">{(a.title || '?').slice(0, 1).toUpperCase()}</div>}
                  <div className="meta"><b>{a.title}</b><span>{a.handle || 'YouTube'}</span></div>
                </div>
              ))}
            </div>
            <div className="hint" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              {selected.length > 1 && voice && <span>🎙️ Voice: <b>{voice.title}</b> (first pick) shapes each generated draft. Same video → all selected channels.</span>}
              <button className="linklike" onClick={onManageAccounts} style={{ marginLeft: 'auto' }}>Manage accounts</button>
            </div>
          </>
        )}
      </div>

      <div className="card">
        <div className="card-title"><span className="dot" />Videos</div>
        <label className="field">Drive folder link, or file links (one per line)</label>
        <textarea rows={6} placeholder={"https://drive.google.com/drive/folders/…\nor\nhttps://drive.google.com/file/d/AAA/view\nhttps://drive.google.com/file/d/BBB/view"} value={input} onChange={(e) => setInput(e.target.value)} />
        <div className="hint">Folder and files must be shared “Anyone with the link”.</div>
      </div>

      <FixedContent fixed={fixed} onChange={setFixed} saved={fixedSaved} />

      <div className="card">
        <div className="card-title"><span className="dot" />Publishing</div>
        <div className="hint" style={{ marginTop: 0, marginBottom: 10 }}>Choose upfront. Nothing is uploaded until you say so.</div>
        <div className="pubgrid">
          <button className={'puboption' + (pub === 'review' ? ' on' : '')} onClick={() => setPub('review')}>
            <b>👀 Review each</b><span>Show me every draft, don’t upload yet</span>
          </button>
          <button className={'puboption' + (pub === 'schedule' ? ' on' : '')} onClick={() => setPub('schedule')}>
            <b>🗓️ Schedule all</b><span>Auto-upload, spaced out from a time I pick</span>
          </button>
          <button className={'puboption' + (pub === 'private' ? ' on' : '')} onClick={() => setPub('private')}>
            <b>🔒 Private</b><span>Upload all now, stay private</span>
          </button>
          <button className={'puboption' + (pub === 'now' ? ' on' : '')} onClick={() => setPub('now')}>
            <b>🌐 Public now</b><span>Upload all &amp; go live immediately</span>
          </button>
        </div>
        {pub === 'schedule' && (
          <div className="row" style={{ marginTop: 14 }}>
            <div>
              <label className="field">First upload time (IST)</label>
              <input type="datetime-local" value={schedAt} onChange={(e) => setSchedAt(e.target.value)} />
            </div>
            <div>
              <label className="field">Gap between videos (min)</label>
              <input type="number" min="0" step="15" value={stagger} onChange={(e) => setStagger(e.target.value)} />
              <div className="hint">Each next video is scheduled this many minutes later.</div>
            </div>
          </div>
        )}
      </div>

      <div className="sticky-bar">
        <button className="btn btn-primary btn-lg" disabled={!canGo} onClick={start}>{resolving ? 'Reading links…' : '✨ Start bulk'}</button>
        <span className="muted">Each video gets its own tab and processes concurrently.</span>
      </div>
    </div>
  )
}
