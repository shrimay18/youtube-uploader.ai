import React, { useEffect, useRef, useState } from 'react'
import { submitFeedback } from '../supabase.js'

const MOODS = [
  { r: 1, e: '😞', label: 'Rough' },
  { r: 2, e: '😕', label: 'Meh' },
  { r: 3, e: '😐', label: 'Okay' },
  { r: 4, e: '😊', label: 'Good' },
  { r: 5, e: '🤩', label: 'Love it' },
]

export default function FeedbackModal({ onClose }) {
  const [anon, setAnon] = useState(false)
  const [rating, setRating] = useState(0)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [mobile, setMobile] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
  const canSend = message.trim().length >= 3 && (anon || (name.trim() && emailOk)) && !busy
  const moodLabel = MOODS.find((m) => m.r === rating)?.label

  async function send() {
    if (!canSend) return
    setBusy(true); setErr('')
    try {
      await submitFeedback({ anonymous: anon, rating, name, email, mobile, message })
      setDone(true)
      setTimeout(onClose, 2000)
    } catch (e) {
      setErr(e.message || 'Something went wrong. Please try again.')
      setBusy(false)
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="fbm" onClick={(e) => e.stopPropagation()}>
        <button className="fbm-x" onClick={onClose} aria-label="Close">✕</button>

        {done ? (
          <div className="fbm-done">
            <div className="fbm-check" aria-hidden="true">
              <svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="23" /><path d="M15 27l7 7 15-16" /></svg>
            </div>
            <h3>Thank you!</h3>
            <p>Your feedback just landed with us. It genuinely shapes what we build next.</p>
          </div>
        ) : (
          <>
            <div className="fbm-top">
              <span className="fbm-badge" aria-hidden="true">💬</span>
              <div className="fbm-titles">
                <h3>Tell us what you think</h3>
                <p>Bugs, ideas, or a love note. We're all ears.</p>
              </div>
            </div>

            <div className="fbm-body">
              {err && <div className="fbm-err">{err}</div>}

              <div className="fbm-block">
                <span className="fbm-q">
                  <span className="fbm-label">How's your experience?</span>
                  {moodLabel && <span className="fbm-qval">{moodLabel}</span>}
                </span>
                <div className="fbm-moods">
                  {MOODS.map((m) => (
                    <button
                      key={m.r}
                      type="button"
                      className={'fbm-mood' + (rating === m.r ? ' on' : '')}
                      onClick={() => setRating(rating === m.r ? 0 : m.r)}
                      title={m.label}
                      aria-pressed={rating === m.r}
                    >
                      <span className="fbm-emoji">{m.e}</span>
                      <span className="fbm-moodlbl">{m.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <label className="fbm-toggle">
                <span className="switch">
                  <input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} />
                  <span className="track" />
                </span>
                <span className="fbm-toggle-txt">
                  <b>Send anonymously</b>
                  <i>{anon ? "We won't know who it's from." : 'Add your details so we can follow up.'}</i>
                </span>
              </label>

              <div className={'fbm-id' + (anon ? ' hide' : '')}>
                <div className="fbm-idwrap">
                  <div className="fbm-grid">
                    <div className="fbm-block">
                      <span className="fbm-label">Name</span>
                      <input type="text" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} />
                    </div>
                    <div className="fbm-block">
                      <span className="fbm-label">Email</span>
                      <input type="email" placeholder="you@email.com" value={email} onChange={(e) => setEmail(e.target.value)} />
                    </div>
                  </div>
                  <div className="fbm-block">
                    <span className="fbm-label">Mobile <span className="fbm-opt">optional</span></span>
                    <input type="tel" placeholder="+91 …" value={mobile} onChange={(e) => setMobile(e.target.value)} />
                  </div>
                </div>
              </div>

              <div className="fbm-block">
                <span className="fbm-label">Your feedback</span>
                <textarea rows={3} placeholder="What's working, what's not, what you wish it did…" value={message} onChange={(e) => setMessage(e.target.value)} />
              </div>
            </div>

            <div className="fbm-foot">
              <button className="fbm-btn ghost" onClick={onClose}>Cancel</button>
              <button className="fbm-btn primary" disabled={!canSend} onClick={send}>
                <span className="fbm-shine" aria-hidden="true" />
                {busy ? 'Sending…' : 'Send feedback'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
