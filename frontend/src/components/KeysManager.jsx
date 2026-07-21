import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { PROVIDERS, KeyHelp } from './KeyGuide.jsx'

const LABEL = Object.fromEntries(PROVIDERS.map((p) => [p.id, p.label]))
const BUILTINS = PROVIDERS.map((p) => p.id)
const newId = () => 'x' + Math.random().toString(36).slice(2, 8)

// Shared keys editor — used by onboarding and settings.
// requireOne: gate save until at least one LLM key exists. submitLabel: primary button text.
export default function KeysManager({ note, onDone, submitLabel = 'Lock in', requireOne = false, secondary }) {
  const [cfg, setCfg] = useState(null)
  const [newKeys, setNewKeys] = useState({}) // { providerId: [committed new key, ...] }
  const [inputs, setInputs] = useState({})   // { providerId: current input text }
  const [removed, setRemoved] = useState({}) // { providerId: Set(indexes of existing to drop) }
  const [order, setOrder] = useState([])
  const [yt, setYt] = useState('')           // new youtube key input
  const [ytClear, setYtClear] = useState(false)
  const [busy, setBusy] = useState(false)
  const [sealing, setSealing] = useState(false)
  const [gtk, setGtk] = useState(false)   // "Good to know" panel
  const [msg, setMsg] = useState('')
  const [dragI, setDragI] = useState(null)
  const [manual, setManual] = useState(false)              // user hand-sorted the priority list
  const [rmCustom, setRmCustom] = useState(() => new Set()) // existing custom indexes to drop
  const [cAdd, setCAdd] = useState([])                      // new custom entries {id,name,model,key}
  const [cForm, setCForm] = useState({ name: '', model: '', key: '' })
  // (YouTube Data API key is app-provided via the deployment env — not entered here.)

  useEffect(() => {
    api.getKeys().then((c) => {
      setCfg(c)
      const cids = (c.custom || []).map((x) => x.id)
      const raw = [...(c.order || BUILTINS), ...BUILTINS, ...cids]
      const valid = new Set([...BUILTINS, ...cids])
      const ord = raw.filter((id, i) => valid.has(id) && raw.indexOf(id) === i)  // dedupe, valid only
      setOrder(ord)
      setNewKeys(Object.fromEntries(PROVIDERS.map((p) => [p.id, []])))
      setInputs(Object.fromEntries(PROVIDERS.map((p) => [p.id, ''])))
    }).catch((e) => setMsg(e.message))
  }, [])

  // Auto-order: providers/customs that HAVE a key float to the top (in priority),
  // ones without sink — unless the user has manually dragged the list.
  useEffect(() => {
    if (!cfg || manual) return
    const has = (id) => BUILTINS.includes(id)
      ? ((cfg.llm[id] || []).filter((_, i) => !(removed[id]?.has(i))).length + (newKeys[id] || []).length > 0)
      : true  // custom ids only remain in `order` while active
    setOrder((o) => {
      const next = [...o.filter(has), ...o.filter((id) => !has(id))]
      return next.join() === o.join() ? o : next
    })
  }, [cfg, manual, newKeys, removed, cAdd, rmCustom])

  if (!cfg) return <div className="stage-line"><div className="spinner" /><span>Loading…</span></div>

  const existing = (id) => cfg.llm[id] || []
  const isRemoved = (id, i) => removed[id]?.has(i)
  const toggleRemove = (id, i) => setRemoved((r) => {
    const s = new Set(r[id] || []); s.has(i) ? s.delete(i) : s.add(i); return { ...r, [id]: s }
  })
  const setInput = (id, v) => setInputs((s) => ({ ...s, [id]: v }))
  const commit = (id) => {
    const v = (inputs[id] || '').trim()
    if (!v) return
    setNewKeys((n) => ({ ...n, [id]: [...(n[id] || []), v] }))
    setInput(id, '')
  }
  const removeNew = (id, i) => setNewKeys((n) => { const l = [...(n[id] || [])]; l.splice(i, 1); return { ...n, [id]: l } })
  const onKeyDownAdd = (id) => (e) => { if (e.key === 'Enter') { e.preventDefault(); commit(id) } }
  const preview = (k) => !k ? '' : (k.length > 12 ? k.slice(0, 6) + '…' + k.slice(-4) : (k.length > 4 ? k.slice(0, 4) + '…' : k))

  const keptCount = (id) => existing(id).filter((_, i) => !isRemoved(id, i)).length
  const addCount = (id) => (newKeys[id] || []).length + ((inputs[id] || '').trim() ? 1 : 0)

  // custom "other AI" providers
  const cExisting = () => cfg.custom || []
  const toggleRmCustom = (i) => {
    const id = cExisting()[i]?.id
    setRmCustom((s) => {
      const n = new Set(s)
      if (n.has(i)) { n.delete(i); if (id) setOrder((o) => o.includes(id) ? o : [...o, id]) }
      else { n.add(i); if (id) setOrder((o) => o.filter((x) => x !== id)) }
      return n
    })
  }
  const setCF = (k, v) => setCForm((f) => ({ ...f, [k]: v }))
  const commitCustom = () => {
    if (!cForm.key.trim() || !cForm.name.trim()) return
    const id = newId()
    setCAdd((a) => [...a, { id, name: cForm.name.trim(), model: cForm.model.trim(), key: cForm.key.trim() }])
    setOrder((o) => [...o, id])
    setCForm({ name: '', model: '', key: '' })
  }
  const removeCAdd = (i) => {
    const id = cAdd[i]?.id
    setCAdd((a) => a.filter((_, j) => j !== i))
    if (id) setOrder((o) => o.filter((x) => x !== id))
  }
  const customCount = () => cExisting().filter((_, i) => !rmCustom.has(i)).length + cAdd.length + (cForm.key.trim() && cForm.name.trim() ? 1 : 0)
  const custName = (id) => (cExisting().find((c) => c.id === id) || cAdd.find((c) => c.id === id) || {}).name
  const labelFor = (id) => LABEL[id] || custName(id) || id
  const hasKey = (id) => BUILTINS.includes(id) ? (keptCount(id) + addCount(id) > 0) : true

  const totalKeys = PROVIDERS.reduce((n, p) => n + keptCount(p.id) + addCount(p.id), 0) + customCount()

  // drag-and-drop reordering
  const onDragStart = (i) => (e) => { setDragI(i); setManual(true); e.dataTransfer.effectAllowed = 'move' }
  const onDragEnter = (i) => () => {
    if (dragI === null || dragI === i) return
    setOrder((o) => { const n = [...o]; const [it] = n.splice(dragI, 1); n.splice(i, 0, it); return n })
    setDragI(i)
  }
  const onDragEnd = () => setDragI(null)

  function buildPayload() {
    const llm = {}
    for (const p of PROVIDERS) {
      const keep = existing(p.id).map((_, i) => i).filter((i) => !isRemoved(p.id, i))
      const add = [...new Set([...(newKeys[p.id] || []), (inputs[p.id] || '').trim()].filter(Boolean))]
      llm[p.id] = { keep, add }
    }
    const cAll = [...cAdd]
    if (cForm.key.trim() && cForm.name.trim()) cAll.push({ id: newId(), name: cForm.name.trim(), model: cForm.model.trim(), key: cForm.key.trim() })
    const custom = { keep: cExisting().map((_, i) => i).filter((i) => !rmCustom.has(i)), add: cAll }
    return { order, youtube: null, llm, custom }   // youtube is app-provided, never set here
  }

  function sparkle(btn) {
    if (!btn || matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const r = btn.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2
    const cols = ['#12b981', '#b6ff3c', '#ffd23f', '#37c6ff', '#ff5a9e', '#ffffff']
    for (let i = 0; i < 20; i++) {
      const s = 4 + Math.random() * 7, d = document.createElement('div')
      d.style.cssText = `position:fixed;left:${cx - s / 2}px;top:${cy - s / 2}px;width:${s}px;height:${s}px;background:${cols[i % cols.length]};border-radius:${Math.random() < 0.5 ? '50%' : '2px'};z-index:99999;pointer-events:none;will-change:transform,opacity`
      document.body.appendChild(d)
      const a = (i / 20) * Math.PI * 2 + Math.random() * 0.5, dist = 70 + Math.random() * 110
      d.animate([
        { transform: 'translate(0,0) scale(1.2) rotate(0)', opacity: 1 },
        { transform: `translate(${Math.cos(a) * dist}px,${Math.sin(a) * dist}px) scale(0) rotate(${Math.random() * 540 - 270}deg)`, opacity: 0 },
      ], { duration: 700 + Math.random() * 450, easing: 'cubic-bezier(.15,.7,.3,1)' }).onfinish = () => d.remove()
    }
  }

  async function save(e) {
    if (requireOne && totalKeys === 0) return
    const btn = e?.currentTarget
    setMsg(''); setBusy(true); setSealing(true)
    sparkle(btn)
    try {
      await api.saveKeys(buildPayload())
      setTimeout(() => onDone?.(), 950)   // let the lock-in celebration play out
    } catch (e2) { setMsg(e2.message); setBusy(false); setSealing(false) }
  }

  return (
    <div className="keysmgr">
      {note && <div className="keys-note">{note}</div>}

      <button type="button" className={'gtk-btn' + (gtk ? ' on' : '')} onClick={() => setGtk((o) => !o)} aria-expanded={gtk}>
        <svg className={'gtk-chev' + (gtk ? ' open' : '')} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
        Good to know
      </button>
      {gtk && (
        <div className="gtk-panel">
          <ul>
            <li>On a budget? <b>Groq</b> has the most generous free tier (fast, high daily limits), a great free fallback.</li>
            <li><b>Google Gemini</b> also has a free tier via Google AI Studio, a solid free default.</li>
            <li><b>Claude</b> and <b>OpenAI</b> are paid but top quality; put a paid key first for the best results.</li>
            <li>Add <b>several keys for the same provider</b> to stack more free quota; we rotate them automatically when one runs out.</li>
            <li>Best of both: a paid key on top, with free keys (Gemini or Groq) below as automatic fallback.</li>
          </ul>
        </div>
      )}

      {msg && <div className="flash bad">{msg}</div>}

      <div className="keys-providers">
        {PROVIDERS.map((p) => (
          <div className="prov" key={p.id}>
            <div className="prov-head">
              <b>{p.label}</b>
              <KeyHelp guide={p} />
            </div>
            {(existing(p.id).length > 0 || (newKeys[p.id] || []).length > 0) && (
              <div className="key-chips">
                {existing(p.id).map((mask, i) => (
                  <span key={'e' + i} className={'key-chip' + (isRemoved(p.id, i) ? ' rm' : '')}>
                    <code>{mask}</code>
                    <button type="button" title={isRemoved(p.id, i) ? 'Undo remove' : 'Remove'} onClick={() => toggleRemove(p.id, i)}>{isRemoved(p.id, i) ? '↺' : '✕'}</button>
                  </span>
                ))}
                {(newKeys[p.id] || []).map((k, i) => (
                  <span key={'n' + i} className="key-chip new">
                    <code>{preview(k)}</code>
                    <button type="button" title="Remove" onClick={() => removeNew(p.id, i)}>✕</button>
                  </span>
                ))}
              </div>
            )}
            <div className="key-add">
              <input type="password" className="key-input" placeholder={`Add a ${p.label} key · ${p.prefix}`}
                value={inputs[p.id] || ''} onChange={(e) => setInput(p.id, e.target.value)} onKeyDown={onKeyDownAdd(p.id)} />
              <button type="button" className="btn btn-primary key-add-btn" disabled={!(inputs[p.id] || '').trim()} onClick={() => commit(p.id)}>Add</button>
            </div>
          </div>
        ))}
      </div>

      {/* Other AI (OpenAI-compatible) */}
      <div className="prov custom-prov">
        <div className="prov-head"><b>Other AI <span className="opt">optional</span></b></div>
        <div className="hint" style={{ marginTop: 0, marginBottom: 10 }}>Any OpenAI-compatible provider. Name it, give the model &amp; key, and it joins your priority list below.</div>
        {(cExisting().length > 0 || cAdd.length > 0) && (
          <div className="custom-list">
            {cExisting().map((c, i) => (
              <div key={'ce' + i} className={'custom-card' + (rmCustom.has(i) ? ' rm' : '')}>
                <div><b>{c.name}</b>{c.model ? <span className="cc-sub">{c.model}</span> : null}<code>{c.key}</code></div>
                <button type="button" onClick={() => toggleRmCustom(i)}>{rmCustom.has(i) ? '↺' : '✕'}</button>
              </div>
            ))}
            {cAdd.map((c, i) => (
              <div key={'ca' + i} className="custom-card new">
                <div><b>{c.name}</b>{c.model ? <span className="cc-sub">{c.model}</span> : null}<code>{preview(c.key)}</code></div>
                <button type="button" onClick={() => removeCAdd(i)}>✕</button>
              </div>
            ))}
          </div>
        )}
        <div className="custom-form">
          <input type="text" className="key-input" placeholder="Name (e.g. OpenRouter)" value={cForm.name} onChange={(e) => setCF('name', e.target.value)} />
          <input type="text" className="key-input" placeholder="Model (e.g. gpt-4o, llama-3.3-70b)" value={cForm.model} onChange={(e) => setCF('model', e.target.value)} />
          <div className="key-add">
            <input type="password" className="key-input" placeholder="API key" value={cForm.key} onChange={(e) => setCF('key', e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commitCustom() } }} />
            <button type="button" className="btn btn-primary key-add-btn" disabled={!(cForm.key.trim() && cForm.name.trim())} onClick={commitCustom}>Add</button>
          </div>
        </div>
      </div>

      {/* Preference order — drag to reorder */}
      <div className="pref">
        <div className="pref-title">Which engine to try first</div>
        <div className="hint" style={{ marginTop: 0 }}>Providers with a key rise to the top automatically. Drag to override. We generate top-to-bottom, skipping any without a key.</div>
        <div className="pref-list">
          {order.map((id, i) => (
            <div className={'pref-row' + (dragI === i ? ' dragging' : '') + (hasKey(id) ? '' : ' nokey')} key={id}
              draggable onDragStart={onDragStart(i)} onDragEnter={onDragEnter(i)}
              onDragOver={(e) => e.preventDefault()} onDragEnd={onDragEnd} onDrop={(e) => e.preventDefault()}>
              <span className="drag-handle" title="Drag to reorder">⠿</span>
              <span className="pref-num">{i + 1}</span>
              <b>{labelFor(id)}</b>
              {!BUILTINS.includes(id) && <span className="pref-tag">custom</span>}
              {hasKey(id) ? <span className="pill-ok">key set</span> : <span className="muted" style={{ fontSize: 12 }}>no key</span>}
            </div>
          ))}
        </div>
      </div>

      <div className="keys-actions">
        <button className={'btn btn-primary btn-lg lockin' + (sealing ? ' sealing' : '')}
          disabled={busy || (requireOne && totalKeys === 0)} onClick={save}>
          <span className="li-shine" aria-hidden="true" />
          <svg className="li-lock" viewBox="0 0 24 26" aria-hidden="true">
            <path className="li-sh" d="M7.5 12 V7.5 a4.5 4.5 0 0 1 9 0 V12" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
            <rect x="4.5" y="11.5" width="15" height="12.5" rx="3.2" fill="currentColor" />
          </svg>
          <span className="li-txt">{sealing ? 'Locked in' : (requireOne && totalKeys === 0) ? 'Add at least one key' : submitLabel}</span>
        </button>
        {secondary}
      </div>
    </div>
  )
}
