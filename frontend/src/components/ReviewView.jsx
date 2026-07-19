import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api, pollJob } from '../api.js'

const CATEGORIES = [
  ['Education', '27'], ['Science & Technology', '28'], ['People & Blogs', '22'],
  ['Howto & Style', '26'], ['Entertainment', '24'], ['Gaming', '20'],
  ['Music', '10'], ['Comedy', '23'], ['News & Politics', '25'],
  ['Film & Animation', '1'], ['Travel & Events', '19'], ['Sports', '17'],
]

const tagChars = (tags) =>
  tags.reduce((n, t, i) => n + t.length + (t.includes(' ') ? 2 : 0) + (i ? 1 : 0), 0)

function scoreClass(s) {
  return s >= 75 ? 'good' : s >= 60 ? 'ok' : 'low'
}

export default function ReviewView({ slug, targetAccounts = [], onManageAccounts, onPublishAll, onBack, onDiscard }) {
  const [d, setD] = useState(null)
  const [flash, setFlash] = useState(null)
  const [saving, setSaving] = useState(false)
  const [thumbV, setThumbV] = useState(0)
  const thumbInput = useRef()

  useEffect(() => {
    api.getDraft(slug).then(setD).catch((e) => setFlash({ t: 'bad', m: e.message }))
  }, [slug])

  const set = (k, v) => setD((prev) => ({ ...prev, [k]: v }))

  const mode = useMemo(() => {
    const pa = String(d?.publish_at || '').trim().toLowerCase()
    if (pa === 'now') return 'now'
    if (!['', 'none', 'keep', 'private', 'unlisted'].includes(pa)) return 'schedule'
    return 'private'
  }, [d])

  if (!d) {
    return (
      <div>
        {onBack && <button className="back" onClick={onBack}>← Back</button>}
        <div className="card"><div className="stage-line"><div className="spinner" /><span>Loading draft…</span></div></div>
      </div>
    )
  }

  const tags = d.tags || []
  const options = d.title_options?.length ? d.title_options : (d.title_variants || []).map((t) => ({ title: t, score: null }))
  const tc = tagChars(tags)
  const tf = d._title_flow || {}

  function setMode(m) {
    if (m === 'now') { set('publish_at', 'now'); set('privacy', 'public') }
    else if (m === 'private') { set('publish_at', 'none'); set('privacy', 'private') }
    else { set('publish_at', d.publish_at && !['now', 'none', ''].includes(d.publish_at) ? d.publish_at : tomorrow6pm()); set('privacy', 'private') }
  }

  const patch = () => ({
    title: d.title, description: d.description, tags: d.tags, hashtags: d.hashtags,
    category_id: d.category_id, category: (CATEGORIES.find((c) => c[1] === String(d.category_id)) || [])[0] || d.category,
    pinned_comment: d.pinned_comment, made_for_kids: !!d.made_for_kids,
    audio_language: d.audio_language, privacy: d.privacy, publish_at: d.publish_at,
  })

  async function save() {
    setSaving(true); setFlash(null)
    try { await api.saveDraft(slug, patch()); setFlash({ t: 'good', m: 'Saved.' }) }
    catch (e) { setFlash({ t: 'bad', m: e.message }) }
    setSaving(false)
  }

  async function publishAll() {
    if (!targetAccounts.length) { setFlash({ t: 'bad', m: 'Select at least one channel to publish to.' }); return }
    const names = targetAccounts.map((a) => a.title).join(', ')
    if (!confirm(`Publish this to ${targetAccounts.length} channel(s) — ${names} — with your current edits?`)) return
    setFlash(null)
    try {
      await api.saveDraft(slug, patch())        // lock in edits before publishing to all
      onPublishAll?.(mode, d.publish_at)
    } catch (e) { setFlash({ t: 'bad', m: e.message }) }
  }

  async function onThumb(e) {
    const f = e.target.files?.[0]
    if (!f) return
    try { await api.uploadThumb(slug, f); setThumbV((v) => v + 1); setFlash({ t: 'good', m: 'Thumbnail replaced.' }) }
    catch (err) { setFlash({ t: 'bad', m: err.message }) }
  }

  const isShort = d._meta?.kind === 'short'

  return (
    <div>
      {onBack && <button className="back" onClick={onBack}>← New upload</button>}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h1 className="hero-title" style={{ marginBottom: 2 }}>Review &amp; publish</h1>
        <span className="pill">{d._meta?.kind}</span>
      </div>
      <p className="hero-sub">Every field is editable. This same content publishes to each channel you pick below.</p>

      {flash && <div className={'flash ' + flash.t}>{flash.m}</div>}

      {/* Target channels */}
      <div className="card">
        <div className="card-title"><span className="dot" />Publishing to {targetAccounts.length ? `· ${targetAccounts.length} channel${targetAccounts.length > 1 ? 's' : ''}` : ''}</div>
        {targetAccounts.length ? (
          <div className="target-chips">
            {targetAccounts.map((a) => (
              <span key={a.id} className="target-chip">
                {a.thumbnail ? <img src={a.thumbnail} alt="" referrerPolicy="no-referrer" /> : <span className="tc-fallback">{(a.title || '?').slice(0, 1)}</span>}
                {a.title}
              </span>
            ))}
          </div>
        ) : (
          <div className="hint" style={{ marginTop: 0 }}>
            No target channels on this draft. <button className="linklike" onClick={onManageAccounts}>Connect / manage accounts</button>.
          </div>
        )}
      </div>

      {/* Title */}
      <div className="card">
        <div className="card-title"><span className="dot" />Title <span className="muted" style={{ textTransform: 'none', letterSpacing: 0, marginLeft: 6 }}>({(d.title || '').length}/100)</span></div>
        <input type="text" maxLength={100} value={d.title || ''} onChange={(e) => set('title', e.target.value)} />
        <div style={{ marginTop: 14 }}>
          {options.map((o, i) => (
            <div key={i} className={'opt' + (o.title === d.title ? ' on' : '')} onClick={() => set('title', o.title)}>
              <span className="radio" />
              {o.score != null && <span className={'score ' + scoreClass(o.score)}>{o.score}</span>}
              <span className="otext">{o.title}</span>
            </div>
          ))}
        </div>
        {(tf.raw_title || tf.ranking_titles?.length) && (
          <details style={{ marginTop: 10 }}>
            <summary>How these titles were made {tf.score != null && `· best SEO score ${tf.score}/100`}</summary>
            {tf.raw_title && <div className="muted" style={{ marginBottom: 6 }}>Raw understanding: <i>{tf.raw_title}</i></div>}
            {tf.reference_title && <div className="muted" style={{ marginBottom: 6 }}>Reference from ranking patterns: <i>{tf.reference_title}</i></div>}
            {tf.ranking_titles?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {tf.ranking_titles.map((r, i) => <span className="pill" key={i}>{r}</span>)}
              </div>
            )}
          </details>
        )}
      </div>

      {/* Description */}
      <div className="card">
        <div className="card-title"><span className="dot" />Description</div>
        <textarea rows={12} value={d.description || ''} onChange={(e) => set('description', e.target.value)} />
      </div>

      {/* Tags + hashtags */}
      <div className="card">
        <div className="card-title"><span className="dot" />Tags <span className={'counter' + (tc > 500 ? ' over' : '')} style={{ marginLeft: 6 }}>{tc}/500</span></div>
        <textarea
          rows={3}
          value={tags.join(', ')}
          onChange={(e) => set('tags', e.target.value.split(/[,\n]/).map((s) => s.trim()).filter(Boolean))}
        />
        <div className="hint">Comma-separated. YouTube caps total tag length at 500 chars.</div>
        <label className="field" style={{ marginTop: 16 }}>Hashtags</label>
        <input type="text" value={(d.hashtags || []).join(', ')} onChange={(e) => set('hashtags', e.target.value.split(/[,\n]/).map((s) => s.trim()).filter(Boolean))} />
      </div>

      <div className="row">
        {/* Thumbnail */}
        <div className="card">
          <div className="card-title"><span className="dot" />Thumbnail</div>
          <div className="thumb-wrap">
            <img className="thumb" src={api.thumbUrl(slug) + '&v=' + thumbV} alt="thumbnail" onError={(e) => (e.target.style.display = 'none')} />
          </div>
          <button className="btn btn-ghost" style={{ marginTop: 12 }} onClick={() => thumbInput.current?.click()}>Replace thumbnail</button>
          <input ref={thumbInput} type="file" accept="image/*" hidden onChange={onThumb} />
          {isShort && <div className="hint">Shorts note: this is the 16:9 thumbnail (search/suggested). The vertical Shorts cover is set in YouTube Studio.</div>}
        </div>

        {/* Category + pinned */}
        <div className="card">
          <div className="card-title"><span className="dot" />Details</div>
          <label className="field">Category</label>
          <select value={String(d.category_id || '27')} onChange={(e) => set('category_id', e.target.value)}>
            {CATEGORIES.map(([n, id]) => <option key={id} value={id}>{n}</option>)}
          </select>
          <label className="field" style={{ marginTop: 14 }}>Pinned comment</label>
          <textarea rows={3} value={d.pinned_comment || ''} onChange={(e) => set('pinned_comment', e.target.value)} />
        </div>
      </div>

      {/* Compliance & language */}
      <div className="card">
        <div className="card-title"><span className="dot" />Compliance &amp; language</div>
        <label className="switch">
          <input type="checkbox" checked={!!d.made_for_kids} onChange={(e) => set('made_for_kids', e.target.checked)} />
          <span className="track" />
          Made for kids (COPPA) — leave off unless child-directed
        </label>
        <div style={{ marginTop: 14, maxWidth: 200 }}>
          <label className="field">Audio language</label>
          <input type="text" value={d.audio_language || ''} onChange={(e) => set('audio_language', e.target.value)} placeholder="hi / en" />
        </div>
        <div className="hint">AI/altered-content disclosure isn’t set here (Studio-only, and this is real footage).</div>
      </div>

      {/* Publish */}
      <div className="card">
        <div className="card-title"><span className="dot" />Publish</div>
        <label className="radio-row"><input type="radio" name="pm" checked={mode === 'private'} onChange={() => setMode('private')} /> Upload &amp; stay <b>&nbsp;private</b>&nbsp; (publish manually later)</label>
        <label className="radio-row"><input type="radio" name="pm" checked={mode === 'now'} onChange={() => setMode('now')} /> Publish <b>&nbsp;now</b>&nbsp; (public immediately)</label>
        <label className="radio-row"><input type="radio" name="pm" checked={mode === 'schedule'} onChange={() => setMode('schedule')} /> Schedule (IST)
          {mode === 'schedule' && <input type="text" style={{ width: 'auto', marginLeft: 10 }} value={d.publish_at} onChange={(e) => set('publish_at', e.target.value)} />}
        </label>
      </div>

      <div className="sticky-bar">
        <button className="btn btn-ghost" onClick={save} disabled={saving}>{saving ? 'Saving…' : '💾 Save'}</button>
        <button className="btn btn-primary" onClick={publishAll} disabled={!targetAccounts.length}>
          ⬆ Publish to {targetAccounts.length || 0} channel{targetAccounts.length === 1 ? '' : 's'}
        </button>
        {onDiscard && (
          <button className="btn btn-danger" onClick={() => { if (confirm('Discard this video? It won’t be uploaded.')) onDiscard() }}>Discard</button>
        )}
        <span className="muted" style={{ marginLeft: 'auto' }}>Same content → every selected channel</span>
      </div>
    </div>
  )
}

function tomorrow6pm() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  d.setHours(18, 0, 0, 0)
  // format as IST-ish RFC3339 (local); backend parses + treats as IST if no tz
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T18:00:00+05:30`
}
