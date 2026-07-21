import React from 'react'
import KeysManager from './KeysManager.jsx'

const NOTE = (
  <>
    <b>Bring your own AI keys.</b> Encrypted on this device, never sent to us.
    <ul>
      <li>Add <b>any number of keys</b> for any provider (a different count per provider is totally fine). We rotate through them automatically.</li>
      <li><b>At least one key</b> across all providers is required to use the tool.</li>
      <li>Providers with a key <b>rise to the top</b> of your priority list. Drag to override anytime.</li>
    </ul>
  </>
)

// Shown right after a first sign-in when no LLM key is set yet.
export default function KeysOnboarding({ onDone }) {
  return (
    <div className="modal-back">
      <div className="modal onboard-modal" onClick={(e) => e.stopPropagation()}>
        <div className="onboard-head">
          <div className="onboard-badge">Welcome 👋</div>
          <h2 className="hero-title" style={{ fontSize: 24, margin: '10px 0 6px' }}>Add your AI keys</h2>
          <p className="hero-sub" style={{ margin: 0 }}>One quick setup and you’re ready to create.</p>
        </div>
        <KeysManager
          note={NOTE}
          requireOne
          submitLabel="Lock in & start"
          onDone={onDone}
          secondary={<button className="btn btn-ghost" onClick={onDone}>I’ll do this later</button>}
        />
        <p className="muted" style={{ textAlign: 'center', marginTop: 12 }}>
          🔒 Keys are encrypted locally with your account. Edit them anytime from the account menu.
        </p>
      </div>
    </div>
  )
}
