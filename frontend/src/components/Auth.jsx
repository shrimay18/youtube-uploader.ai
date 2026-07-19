import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { signInWithGoogle } from '../supabase.js'
import { KEY_GUIDES, KeyField } from './KeyGuide.jsx'

const GoogleG = () => (
  <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.4 29.3 35 24 35c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 5.1 29.6 3 24 3 12.4 3 3 12.4 3 24s9.4 21 21 21 21-9.4 21-21c0-1.2-.1-2.3-.4-3.5z" /><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16 19 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 5.1 29.6 3 24 3 16 3 9.1 7.6 6.3 14.7z" /><path fill="#4CAF50" d="M24 45c5.2 0 9.9-2 13.5-5.2l-6.2-5.3C29.2 35.9 26.7 37 24 37c-5.3 0-9.7-2.5-11.3-6.9l-6.5 5C9.1 40.4 16 45 24 45z" /><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4 5.5l6.2 5.3C41.9 35.6 45 30.3 45 24c0-1.2-.1-2.3-.4-3.5z" /></svg>
)

export default function Auth({ mode, method, hasGoogle, email, onDone, onBack }) {
  const isSignup = mode === 'signup'
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [keys, setKeys] = useState({})
  const [detected, setDetected] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('') // '' | 'password' | 'google'
  const [showKeys, setShowKeys] = useState(false)

  useEffect(() => { if (isSignup) api.envDetected().then(setDetected).catch(() => {}) }, [isSignup])

  async function submitPassword() {
    setError('')
    if (isSignup && password.length < 6) return setError('Password must be at least 6 characters.')
    if (isSignup && password !== password2) return setError('Passwords don’t match.')
    setBusy('password')
    try {
      if (isSignup) await api.setup(password, keys); else await api.login(password)
      onDone()
    } catch (e) { setError(e.message); setBusy('') }
  }

  async function google() {
    setError('')
    setBusy('google')
    // Redirects to Google via Supabase; the app resumes after the redirect back.
    try { await signInWithGoogle() }
    catch (e) { setError(e.message); setBusy('') }
  }

  const showGoogle = isSignup ? hasGoogle : (method === 'google' || hasGoogle)
  const showPassword = isSignup || method !== 'google'

  return (
    <div className="split">
      <aside className="split-brand">
        <div className="split-brand-inner">
          <div className="brand" style={{ marginBottom: 34 }}>
            <div className="mark">▶</div>
            <div><div className="name">youtube_manager<b>.ai</b></div></div>
          </div>
          <h2>{isSignup ? 'A studio that works while you don’t.' : 'Welcome back.'}</h2>
          <p>Set up once. Then drop a video and get a ready-to-publish, SEO-optimized post — in your voice, on your schedule.</p>
          <ul className="split-list">
            <li><span>🔐</span> Keys encrypted on your device — never sent anywhere</li>
            <li><span>🎯</span> Titles &amp; tags built from what actually ranks</li>
            <li><span>📦</span> One video or a whole folder, in parallel</li>
          </ul>
        </div>
        <div className="split-glow" />
      </aside>

      <section className="split-form">
        <button className="back" onClick={onBack}>← Home</button>
        <h1 className="hero-title" style={{ fontSize: 27 }}>{isSignup ? 'Create your account' : 'Sign in'}</h1>
        <p className="hero-sub" style={{ marginBottom: 20 }}>
          {isSignup ? 'It lives entirely on this device.' : (email ? `Signed up as ${email}.` : 'Unlock your encrypted keys.')}
        </p>

        {error && <div className="flash bad">{error}</div>}

        {showGoogle && (
          <>
            <button className="btn-google" disabled={!!busy} onClick={google}>
              <GoogleG /> {busy === 'google' ? 'Redirecting to Google…' : 'Continue with Google'}
            </button>
            {showPassword && <div className="or-div"><span>or</span></div>}
          </>
        )}

        {showPassword && (
          <>
            <label className="field">Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !isSignup) submitPassword() }} autoFocus={!showGoogle} />
            {isSignup && (
              <>
                <label className="field" style={{ marginTop: 12 }}>Confirm password</label>
                <input type="password" value={password2} onChange={(e) => setPassword2(e.target.value)} />
              </>
            )}
          </>
        )}

        {isSignup && (
          <div className="keys-block">
            <button className="keys-toggle" onClick={() => setShowKeys((s) => !s)}>
              {showKeys ? '▾' : '▸'} API keys {Object.values(detected).some(Boolean) && <span className="pill" style={{ marginLeft: 6 }}>some detected from .env</span>}
            </button>
            {showKeys && (
              <div style={{ marginTop: 12 }}>
                <div className="hint" style={{ marginBottom: 12 }}>
                  Two keys are required (Gemini + YouTube) — both free. Each has step-by-step
                  instructions; click “How do I get this?” beside any key.
                </div>
                {KEY_GUIDES.map((g) => (
                  <KeyField key={g.id} guide={g} detected={detected[g.id]}
                    value={keys[g.id]} onChange={(v) => setKeys({ ...keys, [g.id]: v })} />
                ))}
                <div className="hint" style={{ marginTop: 4 }}>You can add or change these anytime from the studio.</div>
              </div>
            )}
          </div>
        )}

        {showPassword && (
          <button className="btn btn-primary btn-block btn-lg" style={{ marginTop: 16 }}
            disabled={!!busy || !password} onClick={submitPassword}>
            {busy === 'password' ? 'Please wait…' : isSignup ? 'Create account' : 'Unlock'}
          </button>
        )}

        <p className="muted" style={{ marginTop: 14, textAlign: 'center' }}>
          🔒 Your password/Google account encrypts your keys locally. No recovery — keep it safe.
        </p>
      </section>
    </div>
  )
}
