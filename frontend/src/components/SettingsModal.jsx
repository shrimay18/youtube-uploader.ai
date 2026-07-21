import React from 'react'
import KeysManager from './KeysManager.jsx'

const NOTE = (
  <>Add <b>any number of keys</b> for any provider (rotated automatically); <b>at least one</b> is required. Providers with a key rise to the top. <b>Drag</b> to override. Everything stays encrypted on this device.</>
)

// A cream "letter" that rises out of a themed envelope — not a modal box.
export default function SettingsModal({ onClose }) {
  return (
    <div className="kv-back" onClick={onClose}>
      <div className="kv-scene" onClick={(e) => e.stopPropagation()}>
        <div className="kv-letter">
          <button className="kv-x" onClick={onClose} title="Close">✕</button>
          <div className="kv-head">
            <div className="kv-badge">🔑</div>
            <h2>API keys &amp; engines</h2>
            <p>Your keys, your models, encrypted on this device.</p>
          </div>
          <KeysManager
            note={NOTE}
            submitLabel="Lock in"
            onDone={onClose}
            secondary={<button className="btn btn-ghost" onClick={onClose}>Close</button>}
          />
          <div className="kv-tuck" aria-hidden="true" />
        </div>
        <div className="kv-pocket" aria-hidden="true">
          <span className="kv-stamp">🔑</span>
          <span className="kv-addr">youtube_manager.ai · encrypted on your device</span>
        </div>
      </div>
    </div>
  )
}
