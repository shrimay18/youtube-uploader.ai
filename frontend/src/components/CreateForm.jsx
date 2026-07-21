import React, { useRef, useState } from 'react'
import FixedContent, { useFixed, appendFixed } from './FixedContent.jsx'

const toIST = (local) => {
  if (!local) return ''
  const d = new Date(local)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00+05:30`
}

export default function CreateForm({ accounts = [], onManageAccounts, onGenerate }) {
  const [selected, setSelected] = useState([])   // target account ids (order = priority; first = voice)
  const [source, setSource] = useState('drive')
  const [driveLink, setDriveLink] = useState('')
  const [videoFile, setVideoFile] = useState(null)
  const [thumbFile, setThumbFile] = useState(null)
  const [thumbLink, setThumbLink] = useState('')
  const [kind, setKind] = useState('auto')
  const [drag, setDrag] = useState(false)
  const [pub, setPub] = useState('review') // review | private | schedule | now
  const [schedAt, setSchedAt] = useState('')
  const [fixed, setFixed, fixedSaved] = useFixed()

  const videoInput = useRef()
  const thumbInput = useRef()

  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])
  const allSelected = accounts.length > 0 && selected.length === accounts.length
  const toggleAll = () => setSelected(allSelected ? [] : accounts.map((a) => a.id))
  const voiceId = selected[0]
  const voice = accounts.find((a) => a.id === voiceId)
  const canGo = selected.length && (source === 'drive' ? driveLink.trim() : videoFile)
    && (pub !== 'schedule' || schedAt)

  function submit() {
    const fd = new FormData()
    if (voiceId) fd.append('voice_account', voiceId)
    fd.append('source_type', source)
    fd.append('force_kind', kind)
    if (source === 'drive') fd.append('drive_link', driveLink.trim())
    else fd.append('video', videoFile)
    if (thumbFile) fd.append('thumbnail', thumbFile)
    else if (thumbLink.trim()) fd.append('thumbnail_link', thumbLink.trim())
    appendFixed(fd, fixed)
    onGenerate(fd, {
      accountIds: selected,
      autoPublish: pub !== 'review',
      publishMode: pub === 'review' ? 'private' : pub,
      publishAt: pub === 'schedule' ? toIST(schedAt) : undefined,
    })
  }

  const onDrop = (e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) setVideoFile(f) }

  return (
    <div>
      <h1 className="hero-title">New upload</h1>
      <p className="hero-sub">Drop a video or paste a Drive link, and youtube_manager writes the title, description, tags &amp; thumbnail.</p>

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
                  <div className="meta"><b>{a.title}</b><span>{a.handle || 'YouTube'}{!a.profile_ok ? ' · set its voice' : ''}</span></div>
                </div>
              ))}
            </div>
            <div className="hint" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              {selected.length > 1 && voice && <span>🎙️ Voice: <b>{voice.title}</b> (first pick) shapes the generated title &amp; description.</span>}
              {selected.length <= 1 && <span>The same video &amp; metadata goes to every channel you select.</span>}
              <button className="linklike" onClick={onManageAccounts} style={{ marginLeft: 'auto' }}>Manage accounts</button>
            </div>
          </>
        )}
      </div>

      <div className="card">
        <div className="card-title"><span className="dot" />Video source</div>
        <div className="segment" style={{ marginBottom: 16 }}>
          <button className={source === 'drive' ? 'on' : ''} onClick={() => setSource('drive')}>Google Drive link</button>
          <button className={source === 'upload' ? 'on' : ''} onClick={() => setSource('upload')}>Upload file</button>
        </div>
        {source === 'drive' ? (
          <>
            <label className="field">Drive share link</label>
            <input type="url" placeholder="https://drive.google.com/file/d/…/view" value={driveLink} onChange={(e) => setDriveLink(e.target.value)} />
            <div className="hint">Set the file to “Anyone with the link”. Short vs long-form is auto-detected by length.</div>
          </>
        ) : (
          <>
            <div className={'dropzone' + (drag ? ' drag' : '')} onClick={() => videoInput.current?.click()} onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={onDrop}>
              {videoFile ? <div className="big file">{videoFile.name}</div> : <><div className="big">Drop a video here, or click to browse</div><div className="small">MP4 / MOV · any length</div></>}
            </div>
            <input ref={videoInput} type="file" accept="video/*" hidden onChange={(e) => setVideoFile(e.target.files?.[0] || null)} />
          </>
        )}
      </div>

      <div className="card">
        <div className="card-title"><span className="dot" />Publishing</div>
        <div className="hint" style={{ marginTop: 0, marginBottom: 10 }}>Choose upfront. Nothing is uploaded until you say so.</div>
        <div className="pubgrid">
          <button className={'puboption' + (pub === 'review' ? ' on' : '')} onClick={() => setPub('review')}>
            <b>👀 Review first</b><span>Show me the draft, don’t upload yet</span>
          </button>
          <button className={'puboption' + (pub === 'schedule' ? ' on' : '')} onClick={() => setPub('schedule')}>
            <b>🗓️ Schedule</b><span>Auto-upload at a time I pick</span>
          </button>
          <button className={'puboption' + (pub === 'private' ? ' on' : '')} onClick={() => setPub('private')}>
            <b>🔒 Private</b><span>Upload now, stays private</span>
          </button>
          <button className={'puboption' + (pub === 'now' ? ' on' : '')} onClick={() => setPub('now')}>
            <b>🌐 Public now</b><span>Upload &amp; go live immediately</span>
          </button>
        </div>
        {pub === 'schedule' && (
          <div style={{ marginTop: 14, maxWidth: 280 }}>
            <label className="field">Upload time (IST)</label>
            <input type="datetime-local" value={schedAt} onChange={(e) => setSchedAt(e.target.value)} />
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title"><span className="dot" />Options</div>
        <label className="field">Format</label>
        <div className="segment">
          <button className={kind === 'auto' ? 'on' : ''} onClick={() => setKind('auto')}>Auto</button>
          <button className={kind === 'short' ? 'on' : ''} onClick={() => setKind('short')}>Short</button>
          <button className={kind === 'long' ? 'on' : ''} onClick={() => setKind('long')}>Long-form</button>
        </div>
        <div className="divider" />
        <label className="field">Thumbnail <span className="muted" style={{ fontWeight: 400 }}>· optional</span></label>
        <div className="row">
          <div><button className="btn btn-ghost btn-block" onClick={() => thumbInput.current?.click()}>{thumbFile ? thumbFile.name : 'Upload thumbnail image'}</button>
            <input ref={thumbInput} type="file" accept="image/*" hidden onChange={(e) => setThumbFile(e.target.files?.[0] || null)} /></div>
          <div><input type="url" placeholder="…or paste a thumbnail link" value={thumbLink} onChange={(e) => setThumbLink(e.target.value)} /></div>
        </div>
      </div>

      <FixedContent fixed={fixed} onChange={setFixed} saved={fixedSaved} />

      <div className="sticky-bar">
        <button className="btn btn-primary btn-lg" disabled={!canGo} onClick={submit}>✨ Generate draft</button>
        <span className="muted">{pub === 'review' ? 'You’ll review the draft before anything is uploaded.' : 'Runs in the background. Add more videos with the + tab.'}</span>
      </div>
    </div>
  )
}
