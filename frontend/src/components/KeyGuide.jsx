import React, { useState } from 'react'

// Everything a newcomer needs to fetch each key, with exact clicks + a direct link.
export const KEY_GUIDES = [
  {
    id: 'GEMINI_API_KEY',
    label: 'Gemini API key',
    required: true,
    badge: 'free',
    tagline: 'Powers the AI that writes your titles, description & tags.',
    url: 'https://aistudio.google.com/apikey',
    urlLabel: 'Open Google AI Studio',
    prefix: 'Starts with “AIza…”',
    steps: [
      'Open Google AI Studio (button below) and sign in with your Google account.',
      'Click “Create API key”.',
      'When asked, let it create a new project (or pick an existing one).',
      'Copy the key it shows and paste it above.',
    ],
    note: 'The free tier is plenty to start — no billing needed.',
  },
  {
    id: 'YOUTUBE_API_KEY',
    label: 'YouTube Data API key',
    required: true,
    badge: 'free',
    tagline: 'Lets us read what’s ranking so your tags & titles match real competitors.',
    url: 'https://console.cloud.google.com/apis/library/youtube.googleapis.com',
    urlLabel: 'Open Google Cloud Console',
    prefix: 'Starts with “AIza…”',
    steps: [
      'Open Google Cloud Console (button below) and pick a project (create one if needed).',
      'On the page that opens, click “Enable” to turn on the YouTube Data API v3.',
      'In the left menu go to APIs & Services → Credentials.',
      'Click “+ Create Credentials” → “API key”.',
      'Copy the key and paste it above. (You can click “Restrict key” → YouTube Data API v3 for safety, but it’s optional.)',
    ],
    note: 'This is a different key from Gemini, even though both look like “AIza…”.',
  },
  {
    id: 'GROQ_API_KEY',
    label: 'Groq API key',
    required: false,
    badge: 'free · optional',
    tagline: 'A free, ultra-fast backup used automatically if Gemini hits its daily limit.',
    url: 'https://console.groq.com/keys',
    urlLabel: 'Open Groq Console',
    prefix: 'Starts with “gsk_…”',
    steps: [
      'Open the Groq Console (button below) and sign up — it’s free.',
      'Click “Create API Key”, give it any name.',
      'Copy the key immediately (you can’t see it again) and paste it above.',
    ],
    note: 'Optional, but recommended so you never get blocked mid-batch.',
  },
  {
    id: 'ANTHROPIC_API_KEY',
    label: 'Anthropic (Claude) key',
    required: false,
    badge: 'paid · optional',
    tagline: 'Only if you’d like to use Claude as the writing engine.',
    url: 'https://console.anthropic.com/settings/keys',
    urlLabel: 'Open Anthropic Console',
    prefix: 'Starts with “sk-ant-…”',
    steps: [
      'Open the Anthropic Console (button below) and sign in.',
      'Go to Settings → API Keys → “Create Key”.',
      'Copy the key and paste it above.',
    ],
    note: 'Skip this unless you specifically want Claude. It requires a paid Anthropic account.',
  },
]

const ExternalIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><path d="M15 3h6v6" /><path d="M10 14 21 3" /></svg>
)

// One key: label + input + a "How do I get this?" collapsible with exact steps.
export function KeyField({ guide, value, detected, onChange }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="keyfield">
      <div className="keyfield-top">
        <label className="field" style={{ margin: 0 }}>
          {guide.label}
          <span className={`pill pill-${guide.required ? 'req' : 'opt'}`}>{guide.badge}</span>
          {detected && <span className="pill pill-ok">detected from .env</span>}
        </label>
        <button type="button" className="how-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? 'Hide steps' : 'How do I get this?'}
        </button>
      </div>
      <div className="keyfield-tag">{guide.tagline}</div>
      <input
        type="password"
        placeholder={detected ? '•••• using your .env key — leave blank to keep it' : guide.prefix}
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
      />
      {open && (
        <div className="how-panel">
          <ol className="how-steps">
            {guide.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>
          <a className="how-link" href={guide.url} target="_blank" rel="noreferrer">
            <ExternalIcon /> {guide.urlLabel}
          </a>
          {guide.note && <div className="how-note">💡 {guide.note}</div>}
        </div>
      )}
    </div>
  )
}
