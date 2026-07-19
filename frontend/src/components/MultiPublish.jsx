import React from 'react'

function Avatar({ a }) {
  if (a?.thumbnail) return <img className="yt-avatar sm" src={a.thumbnail} alt="" referrerPolicy="no-referrer" />
  return <div className="yt-avatar sm fallback">{(a?.title || '?').slice(0, 1).toUpperCase()}</div>
}

export default function MultiPublish({ item, targetAccounts, onCancel }) {
  const results = item.results || {}
  const targets = targetAccounts?.length ? targetAccounts : Object.keys(results).map((id) => ({ id, title: 'Channel' }))
  const done = item.status === 'published'
  const okCount = Object.values(results).filter((r) => r.status === 'published').length
  const errCount = Object.values(results).filter((r) => r.status === 'error').length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <h1 className="hero-title" style={{ marginBottom: 2 }}>
          {done ? 'Publishing complete' : 'Publishing to YouTube'}
        </h1>
        <span className="pill">{okCount}/{targets.length} done{errCount ? ` · ${errCount} failed` : ''}</span>
      </div>
      <p className="hero-sub">Same video, each of your selected channels.</p>

      <div className="card">
        <div className="pub-targets">
          {targets.map((a) => {
            const r = results[a.id] || { status: 'idle' }
            return (
              <div key={a.id} className={'pub-target st-' + r.status}>
                <Avatar a={a} />
                <div className="pt-meta">
                  <b>{a.title}</b>
                  <span>
                    {r.status === 'published' && r.url
                      ? <a href={r.url} target="_blank" rel="noreferrer">{r.url}</a>
                      : r.status === 'error' ? <span className="warn-text">{r.error || 'Failed'}</span>
                        : r.status === 'publishing' ? (r.stage || 'Uploading…')
                          : 'Waiting…'}
                  </span>
                </div>
                <div className="pt-state">
                  {r.status === 'published' ? '✓'
                    : r.status === 'error' ? '⚠'
                      : r.status === 'publishing' ? <span className="spinner sm" />
                        : '•'}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {done && (
        <div className="sticky-bar">
          {okCount > 0 && <span className="muted">✓ Uploaded to {okCount} channel{okCount > 1 ? 's' : ''}.</span>}
          <button className="btn btn-ghost" style={{ marginLeft: 'auto' }} onClick={onCancel}>Close tab</button>
        </div>
      )}
    </div>
  )
}
