import React, { useState } from 'react'

// LLM providers you can add keys for (order = default preference). No free/paid labels.
export const PROVIDERS = [
  {
    id: 'anthropic', label: 'Anthropic (Claude)', prefix: 'e.g. sk-ant-api03-…',
    url: 'https://console.anthropic.com/settings/keys', urlLabel: 'Open Anthropic Console',
    steps: [
      'Open the Anthropic Console and sign in.',
      'Go to Settings → API Keys → “Create Key”.',
      'Copy the key and paste it above.',
    ],
  },
  {
    id: 'gemini', label: 'Google Gemini', prefix: 'e.g. AIzaSy…',
    url: 'https://aistudio.google.com/apikey', urlLabel: 'Open Google AI Studio',
    steps: [
      'Open Google AI Studio and sign in with Google.',
      'Click “Create API key” and pick or create a project.',
      'Copy the key and paste it above.',
    ],
  },
  {
    id: 'openai', label: 'OpenAI (GPT)', prefix: 'e.g. sk-proj-… or sk-…',
    url: 'https://platform.openai.com/api-keys', urlLabel: 'Open OpenAI Platform',
    steps: [
      'Open the OpenAI API keys page and sign in.',
      'Click “Create new secret key” and name it.',
      'Copy the key immediately (shown once) and paste it above.',
    ],
  },
  {
    id: 'groq', label: 'Groq', prefix: 'e.g. gsk_…',
    url: 'https://console.groq.com/keys', urlLabel: 'Open Groq Console',
    steps: [
      'Open the Groq Console and sign up (free).',
      'Click “Create API Key” and give it any name.',
      'Copy the key and paste it above.',
    ],
  },
]

export const YT_GUIDE = {
  id: 'youtube', label: 'YouTube Data API key', prefix: 'starts with “AIza…”',
  url: 'https://console.cloud.google.com/apis/library/youtube.googleapis.com',
  urlLabel: 'Open Google Cloud Console',
  steps: [
    'Open Google Cloud Console (button below) and pick/create a project.',
    'Click “Enable” to turn on the YouTube Data API v3.',
    'Go to APIs & Services → Credentials → “+ Create Credentials” → “API key”.',
    'Copy the key and paste it here.',
  ],
  note: 'Optional. It powers competitor research (matching tags/titles to what ranks). Without it, generation still works, just without ranking optimization.',
}

const ExternalIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><path d="M15 3h6v6" /><path d="M10 14 21 3" /></svg>
)

const Chevron = ({ open }) => (
  <svg className={'how-chev' + (open ? ' open' : '')} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
)

// Collapsible "How do I get this?" panel for a provider.
export function KeyHelp({ guide }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" className={'how-btn' + (open ? ' on' : '')} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Chevron open={open} /> How do I get a key?
      </button>
      {open && (
        <div className="how-panel">
          <ol className="how-steps">
            {guide.steps.map((s, i) => (
              <li key={i}><span className="how-n">{i + 1}</span><span>{s}</span></li>
            ))}
          </ol>
          <a className="how-link" href={guide.url} target="_blank" rel="noreferrer">{guide.urlLabel} <ExternalIcon /></a>
          {guide.note && <div className="how-note">{guide.note}</div>}
        </div>
      )}
    </>
  )
}
