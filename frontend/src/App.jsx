import React, { useEffect, useState } from 'react'
import { api } from './api.js'
import { getSupabase, getSession, signOut as sbSignOut, logEvent } from './supabase.js'
import Studio from './Studio.jsx'
import Landing from './components/Landing.jsx'
import Auth from './components/Auth.jsx'
import SettingsModal from './components/SettingsModal.jsx'
import AdminModal from './components/AdminModal.jsx'
import FeedbackModal from './components/FeedbackModal.jsx'
import KeysOnboarding from './components/KeysOnboarding.jsx'
import YouTubeAccounts from './components/YouTubeAccounts.jsx'
import Legal from './components/Legal.jsx'

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute('data-theme') || 'dark')
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('tm-theme', theme)
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}

const Sun = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" /></svg>)
const Moon = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>)

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const [status, setStatus] = useState(null) // {account_exists, authed}
  const [view, setView] = useState('landing') // landing | signup | login | studio
  const [settings, setSettings] = useState(false)
  const [admin, setAdmin] = useState(false)
  const [feedback, setFeedback] = useState(false)
  const [ytAccounts, setYtAccounts] = useState(false)
  const [menu, setMenu] = useState(false)
  const [needsKeys, setNeedsKeys] = useState(false)
  const [accountsTick, setAccountsTick] = useState(0) // bump to refresh Studio's account list
  const [booting, setBooting] = useState(true) // hold the loading screen until the auto-unlock resolves

  // After sign-in, prompt for keys if no LLM key is set yet.
  async function checkKeys() {
    try {
      const m = await api.getKeys()
      setNeedsKeys(!m.has_llm)
    } catch { /* not authed yet */ }
  }

  const refresh = () => api.authStatus().then((s) => {
    setStatus(s)
    if (s.authed) { setView('studio'); checkKeys() }
    return s
  }).catch(() => { const s = { account_exists: false, authed: false }; setStatus(s); return s })

  // Trade a Supabase session for a local vault unlock, then show the studio.
  async function unlockFromSession(session) {
    if (!session?.access_token) return false
    try {
      await api.supabaseLogin(session.access_token)
      await refresh()
      logEvent('app_open')
      return true
    } catch { return false }
  }

  useEffect(() => {
    let unsub = null
    ;(async () => {
      const s = await refresh()
      // If a Google session is already present (or arrives via OAuth redirect),
      // unlock the vault. The vault is in-memory, so this also re-unlocks after a
      // server restart while the browser session persists.
      if (!s.authed) {
        const session = await getSession().catch(() => null)
        if (session) await unlockFromSession(session)
      }
      // Auto-unlock has resolved — now it's safe to reveal the landing (if truly
      // signed out) without flashing it at a returning, already-signed-in user.
      setBooting(false)
      const sb = await getSupabase().catch(() => null)
      if (sb) {
        const { data } = sb.auth.onAuthStateChange((event, session) => {
          if (event === 'SIGNED_IN' && session) unlockFromSession(session)
        })
        unsub = data?.subscription
      }
    })()
    return () => { try { unsub?.unsubscribe() } catch {} }
  }, [])

  const authed = status?.authed
  const goStart = () => setView(status?.account_exists ? 'login' : 'signup')

  async function logout() {
    setMenu(false)
    await sbSignOut().catch(() => {})
    await api.logout().catch(() => {})
    setStatus((s) => ({ ...s, authed: false }))
    setView('landing')
  }

  async function resetAccount() {
    if (!confirm('Reset this account on this device?\n\nThis permanently removes EVERYTHING stored here: your API keys, connected YouTube channels, the fixed description & pinned comment, and all drafts. It becomes a brand-new account. (Any keys in a local .env are re-detected.)\n\nThis cannot be undone.')) return
    setMenu(false)
    await sbSignOut().catch(() => {})
    await api.reset().catch(() => {})
    try { localStorage.removeItem('tm-workspace'); localStorage.removeItem('tm-fixed') } catch {}
    const s = await api.authStatus().catch(() => ({ account_exists: false, authed: false }))
    setStatus(s)
    setView('landing')
  }

  // The funky public pages carry their own nav/footer, so hide the studio topbar there.
  const publicView = ['landing', 'privacy', 'terms'].includes(view)

  return (
    <div className="app">
      {!publicView && (
      <header className="topbar">
        <div className="brand" style={{ cursor: 'pointer' }} onClick={() => setView(authed ? 'studio' : 'landing')}>
          <div className="mark">▶</div>
          <div>
            <div className="name">youtube_manager<b>.ai</b></div>
            <div className="tag">AI YouTube Manager</div>
          </div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
          {authed && (
            <button className="btn btn-ghost keys-btn" onClick={() => setSettings(true)} title="Your API keys & engines">
              <span className="keys-btn-ic">🔑</span><span className="keys-btn-txt">API keys</span>
            </button>
          )}
          {authed && (
            <div className="acct">
              <button className="btn btn-ghost acct-btn" onClick={() => setMenu((m) => !m)}>
                <span className="acct-email">{status?.email ? status.email : 'Account'}</span>
                <span className="acct-caret">▾</span>
              </button>
              {menu && (
                <>
                  <div className="acct-scrim" onClick={() => setMenu(false)} />
                  <div className="acct-menu">
                    {status?.is_admin && (
                      <button onClick={() => { setAdmin(true); setMenu(false) }}>Admin dashboard</button>
                    )}
                    <button onClick={logout}>Log out</button>
                    <div className="acct-sep" />
                    <button className="danger" onClick={resetAccount}>⚠ Reset account</button>
                  </div>
                </>
              )}
            </div>
          )}
          {!authed && status?.account_exists && view === 'landing' && (
            <button className="btn btn-ghost" onClick={() => setView('login')}>Sign in</button>
          )}
          <button className="btn btn-ghost fb-topbtn" onClick={() => setFeedback(true)} title="Send feedback">Feedback</button>
          <button className="icon-btn" onClick={toggleTheme} title="Toggle theme">
            {theme === 'dark' ? <Sun /> : <Moon />}
          </button>
        </div>
      </header>
      )}

      {!status || booting ? (
        <main className="container"><div className="card"><div className="stage-line"><div className="spinner" /><span>Loading…</span></div></div></main>
      ) : authed && view === 'studio' ? (
        <Studio accountsTick={accountsTick} onManageAccounts={() => setYtAccounts(true)} />
      ) : view === 'signup' || view === 'login' ? (
        <Auth mode={view} method={status.method} hasGoogle={status.has_google}
          email={status.email} onDone={refresh} onBack={() => setView('landing')} />
      ) : view === 'privacy' || view === 'terms' ? (
        <Legal page={view} onHome={() => setView('landing')} onNav={(p) => setView(p)} />
      ) : (
        <Landing accountExists={status.account_exists} onGetStarted={goStart}
          onSignIn={() => setView('login')} onNav={(p) => setView(p)} onFeedback={() => setFeedback(true)}
          theme={theme} onToggleTheme={toggleTheme} />
      )}

      {settings && <SettingsModal onClose={() => setSettings(false)} />}
      {admin && <AdminModal onClose={() => setAdmin(false)} />}
      {feedback && <FeedbackModal onClose={() => setFeedback(false)} />}
      {ytAccounts && <YouTubeAccounts onClose={() => setYtAccounts(false)} onChanged={() => setAccountsTick((t) => t + 1)} />}
      {authed && needsKeys && <KeysOnboarding onDone={() => setNeedsKeys(false)} />}
    </div>
  )
}
