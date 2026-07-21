import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

function fmtDate(s) {
  if (!s) return '-'
  const d = new Date(s)
  if (isNaN(d)) return '-'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function fmtAgo(s) {
  if (!s) return '-'
  const d = new Date(s)
  if (isNaN(d)) return '-'
  const mins = Math.floor((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

const MOOD = { 1: '😞', 2: '😕', 3: '😐', 4: '😊', 5: '🤩' }

export default function AdminModal({ onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [reviews, setReviews] = useState(null)

  useEffect(() => {
    api.adminStats().then(setData).catch((e) => setError(e.message))
    api.adminFeedback().then((r) => setReviews(r.feedback || [])).catch(() => setReviews([]))
  }, [])

  const t = data?.totals
  const maxDay = Math.max(1, ...(data?.series_14d || []).map((d) => d.count))

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal admin-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'flex-start' }}>
          <div>
            <h2 className="hero-title" style={{ fontSize: 22, margin: 0 }}>Admin dashboard</h2>
            <p className="hero-sub" style={{ margin: '6px 0 0' }}>Usage across all users. Live from Supabase.</p>
          </div>
          <button className="icon-btn" style={{ marginLeft: 'auto' }} onClick={onClose} title="Close">✕</button>
        </div>

        {error && <div className="flash bad">{error}</div>}
        {!data && !error && <div className="stage-line"><div className="spinner" /><span>Loading…</span></div>}

        {data && (
          <>
            <div className="stat-grid">
              <Stat label="Total users" value={t.users} />
              <Stat label="New (30d)" value={t.signups_30d} />
              <Stat label="Active (7d)" value={t.active_7d} />
              <Stat label="Generations" value={t.generations} />
              <Stat label="Publishes" value={t.publishes} />
              <Stat label="Events (7d)" value={t.events_7d} />
            </div>

            <div className="admin-section">
              <div className="admin-section-title">Activity · last 14 days</div>
              <div className="chart">
                {data.series_14d.map((d) => (
                  <div className="chart-col" key={d.day} title={`${d.day}: ${d.count}`}>
                    <div className="chart-bar" style={{ height: `${(d.count / maxDay) * 100}%` }}>
                      {d.count > 0 && <span className="chart-val">{d.count}</span>}
                    </div>
                    <div className="chart-x">{d.day.slice(5)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="admin-section">
              <div className="admin-section-title">Users ({data.users.length})</div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr><th>Email</th><th>Joined</th><th>Last active</th><th>Gen</th><th>Pub</th></tr>
                  </thead>
                  <tbody>
                    {data.users.map((u, i) => (
                      <tr key={i}>
                        <td>
                          <div className="u-email">{u.email}</div>
                          {u.name && <div className="u-name">{u.name}</div>}
                        </td>
                        <td>{fmtDate(u.created_at)}</td>
                        <td>{fmtAgo(u.last_active)}</td>
                        <td className="num">{u.generations}</td>
                        <td className="num">{u.publishes}</td>
                      </tr>
                    ))}
                    {data.users.length === 0 && (
                      <tr><td colSpan="5" className="muted" style={{ textAlign: 'center', padding: 24 }}>No users yet.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="admin-section">
              <div className="admin-section-title">Feedback ({reviews ? reviews.length : '…'})</div>
              {!reviews && <div className="stage-line"><div className="spinner" /><span>Loading…</span></div>}
              {reviews && reviews.length === 0 && (
                <div className="muted" style={{ padding: '10px 2px' }}>No feedback yet.</div>
              )}
              {reviews && reviews.length > 0 && (
                <div className="fb-list">
                  {reviews.map((r) => (
                    <div className="fb-item" key={r.id}>
                      <div className="fb-item-top">
                        {r.rating ? <span className="fb-item-mood">{MOOD[r.rating] || ''}</span> : null}
                        <span className="fb-item-who">
                          {r.anonymous ? 'Anonymous' : (r.name || r.email || 'User')}
                        </span>
                        <span className="fb-item-date">{fmtDate(r.created_at)}</span>
                      </div>
                      <div className="fb-item-msg">{r.message}</div>
                      {!r.anonymous && (r.email || r.mobile) && (
                        <div className="fb-item-contact">
                          {r.email && <span>✉ {r.email}</span>}
                          {r.mobile && <span>📞 {r.mobile}</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}
