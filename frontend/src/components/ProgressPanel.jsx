import React from 'react'

export default function ProgressPanel({ title, sub, stage, log }) {
  return (
    <div>
      <h1 className="hero-title">{title}</h1>
      <p className="hero-sub">{sub}</p>
      <div className="card">
        <div className="stage-line">
          <div className="spinner" />
          <div className="stage-text">{stage || 'Starting…'}</div>
        </div>
        <div className="log">
          {(!log || log.length === 0) && <div className="l muted">Starting…</div>}
          {(log || []).map((l, i) => <div className="l" key={i}>{l}</div>)}
        </div>
      </div>
    </div>
  )
}
