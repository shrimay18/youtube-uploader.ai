import React, { useEffect, useState, useCallback, useRef } from 'react'
import { api, pollJob } from './api.js'
import { logEvent } from './supabase.js'
import CreateForm from './components/CreateForm.jsx'
import BulkSetup from './components/BulkSetup.jsx'
import ProgressPanel from './components/ProgressPanel.jsx'
import ReviewView from './components/ReviewView.jsx'
import MultiPublish from './components/MultiPublish.jsx'

const STORE = 'tm-workspace'
let SEQ = 1
const publishPatch = (mode, publishAt) =>
  mode === 'now' ? { privacy: 'public', publish_at: 'now' }
    : mode === 'schedule' ? { privacy: 'private', ...(publishAt ? { publish_at: publishAt } : {}) }
      : { privacy: 'private', publish_at: 'none' }

const staggered = (local, gapMin, i) => {
  if (!local) return ''
  const d = new Date(local)
  d.setMinutes(d.getMinutes() + i * (gapMin || 0))
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00+05:30`
}

const slim = (it) => { const { log, stage, ...rest } = it; return rest }
const statusIcon = (s) => ({ new: '•', queued: '⏳', generating: '⏳', ready: '✎', publishing: '⬆', published: '✓', error: '⚠' }[s] || '•')

export default function Studio({ accountsTick, onManageAccounts }) {
  const [accounts, setAccounts] = useState([])
  const [mode, setMode] = useState('single')
  const [items, setItems] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [booted, setBooted] = useState(false)
  const cancelled = useRef(new Set())

  useEffect(() => { api.ytAccounts().then(setAccounts).catch(() => setAccounts([])) }, [accountsTick])

  const patchItem = useCallback((id, patch) => {
    setItems((prev) => prev.map((it) => (it.id === id
      ? { ...it, ...(typeof patch === 'function' ? patch(it) : patch) } : it)))
  }, [])

  const setResult = useCallback((id, accountId, patch) => {
    patchItem(id, (it) => ({ results: { ...(it.results || {}), [accountId]: { ...((it.results || {})[accountId] || {}), ...patch } } }))
  }, [patchItem])

  const addBlank = useCallback(() => {
    const id = SEQ++
    setItems((prev) => [...prev, { id, status: 'new', label: `Video ${prev.length + 1}`, log: [] }])
    setActiveId(id)
    return id
  }, [])

  // Publish one draft to every selected account, tracking per-account status.
  const runMultiPublish = useCallback(async (id, slug, accountIds, pmode, publishAt) => {
    if (cancelled.current.has(id) || !accountIds?.length) return
    patchItem(id, { status: 'publishing' })
    for (const accountId of accountIds) {
      if (cancelled.current.has(id)) return
      setResult(id, accountId, { status: 'publishing', log: [] })
      try {
        const { job_id } = await api.publish(slug, { ...publishPatch(pmode, publishAt), account_id: accountId })
        const job = await pollJob(job_id, (j) => setResult(id, accountId, { log: j.log, stage: j.stage }))
        setResult(id, accountId, { status: 'published', url: job.result?.url })
        logEvent('publish')
      } catch (e) {
        setResult(id, accountId, { status: 'error', error: e.message })
      }
    }
    patchItem(id, { status: 'published' })
  }, [patchItem, setResult])

  const runGenerate = useCallback(async (id, formData, plan) => {
    patchItem(id, { status: 'generating', stage: 'Uploading…', log: [], error: null, plan,
      accountIds: plan.accountIds, results: {} })
    try {
      const { job_id } = await api.generate(formData)
      patchItem(id, { jobId: job_id })
      const job = await pollJob(job_id, (j) => patchItem(id, { stage: j.stage, log: j.log }))
      const slug = job.result.slug
      patchItem(id, { status: 'ready', slug, label: job.result.title || 'Untitled' })
      logEvent('generate')
      if (plan?.autoPublish && !cancelled.current.has(id)) runMultiPublish(id, slug, plan.accountIds, plan.publishMode, plan.publishAt)
    } catch (e) { patchItem(id, { status: 'error', error: e.message }) }
  }, [patchItem, runMultiPublish])

  const ranRestore = useRef(false)
  useEffect(() => {
    if (ranRestore.current) return
    ranRestore.current = true
    let saved = null
    try { saved = JSON.parse(localStorage.getItem(STORE) || 'null') } catch {}
    const restored = saved?.items || []
    if (restored.length) {
      SEQ = Math.max(...restored.map((i) => i.id), 0) + 1
      setItems(restored.map((i) => ({ ...i, log: [] })))
      setMode(saved.mode || 'single')
      setActiveId(saved.activeId ?? restored[0].id)
    }
    setBooted(true)

    restored.forEach(async (it) => {
      const busy = ['generating', 'queued'].includes(it.status)
      if (busy && it.jobId) {
        try {
          const jj = await api.job(it.jobId)
          if (jj.status === 'running') {
            const done = await pollJob(it.jobId, (k) => patchItem(it.id, { stage: k.stage, log: k.log }))
            patchItem(it.id, { status: 'ready', slug: done.result.slug, label: done.result.title || it.label })
            return
          }
          if (jj.status === 'done') {
            patchItem(it.id, { status: 'ready', slug: jj.result?.slug || it.slug, label: jj.result?.title || it.label })
            return
          }
          if (jj.status === 'error') { patchItem(it.id, { status: 'error', error: jj.error }); return }
        } catch {}
      }
      if ((busy || it.status === 'ready') && it.slug) {
        try {
          const d = await api.getDraft(it.slug)
          const published = d._meta?.video_id || Object.keys(d._meta?.publishes || {}).length
          patchItem(it.id, { status: published ? (it.status === 'publishing' ? 'published' : it.status) : it.status, label: d.title || it.label })
        } catch { if (busy) patchItem(it.id, { status: 'error', error: 'Lost on restart — please retry.' }) }
      } else if (busy) {
        patchItem(it.id, { status: 'error', error: 'Lost on restart — please retry.' })
      }
    })
  }, [patchItem])

  useEffect(() => {
    if (!booted) return
    try { localStorage.setItem(STORE, JSON.stringify({ mode, activeId, items: items.map(slim) })) } catch {}
  }, [items, mode, activeId, booted])

  useEffect(() => {
    if (booted && mode === 'single' && items.length === 0) addBlank()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [booted, mode, items.length])

  async function startBulk(videos, { accountIds, voiceId, autoPublish, publishMode, schedAt, stagger, fixed }) {
    const created = videos.map((v) => ({ id: SEQ++, status: 'queued', label: v.name || v.link, log: [], accountIds, results: {} }))
    setItems(created)
    setActiveId(created[0]?.id ?? null)
    created.forEach((it, i) => {
      const fd = new FormData()
      if (voiceId) fd.append('voice_account', voiceId)
      fd.append('source_type', 'drive')
      fd.append('drive_link', videos[i].link)
      fd.append('force_kind', 'auto')
      if (videos[i].name) fd.append('name', videos[i].name)
      if (fixed) {
        fd.append('fixed_desc_text', fixed.descText || '')
        fd.append('fixed_desc_position', fixed.descPos || 'auto')
        fd.append('fixed_comment_text', fixed.commentText || '')
        fd.append('fixed_comment_mode', fixed.commentMode || 'ai')
      }
      const publishAt = publishMode === 'schedule' ? staggered(schedAt, stagger, i) : undefined
      runGenerate(it.id, fd, { accountIds, autoPublish, publishMode, publishAt })
    })
  }

  function cancelItem(id) {
    cancelled.current.add(id)
    const it = items.find((x) => x.id === id)
    setItems((prev) => {
      const next = prev.filter((x) => x.id !== id)
      if (activeId === id) setActiveId(next[next.length - 1]?.id ?? null)
      return next
    })
    const anyPublished = it?.results && Object.values(it.results).some((r) => r.status === 'published')
    if (it?.slug && it.status !== 'published' && !anyPublished) api.deleteDraft(it.slug).catch(() => {})
  }

  const switchMode = (m) => { if (m !== mode) { setMode(m); setItems([]); setActiveId(null) } }
  const active = items.find((it) => it.id === activeId)
  const acctsFor = (ids) => (ids || []).map((id) => accounts.find((a) => a.id === id)).filter(Boolean)

  return (
    <div className="container">
      <div className="studio-head">
        <div className="segment mode-toggle">
          <button className={mode === 'single' ? 'on' : ''} onClick={() => switchMode('single')}>Single Upload</button>
          <button className={mode === 'bulk' ? 'on' : ''} onClick={() => switchMode('bulk')}>Bulk Upload</button>
        </div>
      </div>

      {mode === 'bulk' && items.length === 0 ? (
        <BulkSetup accounts={accounts} onManageAccounts={onManageAccounts} onStart={startBulk} />
      ) : (
        <>
          {items.length > 0 && (
            <div className="tabbar">
              {items.map((it) => (
                <span key={it.id} className={'vtab' + (it.id === activeId ? ' on' : '') + (it.status === 'error' ? ' err' : '')}>
                  <button className="vt-main" onClick={() => setActiveId(it.id)} title={it.label}>
                    <span className={'vt-ico st-' + it.status}>{statusIcon(it.status)}</span>
                    <span className="vt-label">{it.label}</span>
                  </button>
                  {it.status !== 'published' && (
                    <button className="vt-x" title="Cancel / discard" onClick={() => cancelItem(it.id)}>✕</button>
                  )}
                </span>
              ))}
              {mode === 'single' && <button className="vtab add" onClick={addBlank} title="Add another video">+</button>}
            </div>
          )}
          {active && (
            <ItemView
              key={active.id}
              item={active}
              accounts={accounts}
              targetAccounts={acctsFor(active.accountIds)}
              onManageAccounts={onManageAccounts}
              onGenerate={(fd, plan) => runGenerate(active.id, fd, plan)}
              onPublishAll={(pmode, publishAt) => runMultiPublish(active.id, active.slug, active.accountIds, pmode, publishAt)}
              onDone={() => patchItem(active.id, { status: 'published' })}
              onRetry={() => patchItem(active.id, { status: 'new' })}
              onCancel={() => cancelItem(active.id)}
            />
          )}
        </>
      )}
    </div>
  )
}

function ItemView({ item, accounts, targetAccounts, onManageAccounts, onGenerate, onPublishAll, onDone, onRetry, onCancel }) {
  if (item.status === 'new')
    return <CreateForm accounts={accounts} onManageAccounts={onManageAccounts} onGenerate={onGenerate} />
  if (item.status === 'queued' || item.status === 'generating')
    return (
      <div>
        <ProgressPanel title="Creating your draft" sub="Transcribing, researching top-ranking videos, writing SEO metadata…" stage={item.stage} log={item.log} />
        <button className="btn btn-ghost" style={{ marginTop: 14 }} onClick={onCancel}>✕ Cancel</button>
      </div>
    )
  if (item.status === 'error')
    return (
      <div className="card">
        <div className="flash bad">Failed: {item.error}</div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-ghost" onClick={onRetry}>← Try again</button>
          <button className="btn btn-ghost" onClick={onCancel}>Discard</button>
        </div>
      </div>
    )
  // publishing (direct) or published -> per-account status panel
  if (item.status === 'publishing' || item.status === 'published')
    return <MultiPublish item={item} targetAccounts={targetAccounts} onCancel={onCancel} />
  // ready -> review, then publish per account
  return (
    <ReviewView
      slug={item.slug}
      targetAccounts={targetAccounts}
      results={item.results}
      onManageAccounts={onManageAccounts}
      onPublishAll={onPublishAll}
      onDiscard={onCancel}
    />
  )
}
