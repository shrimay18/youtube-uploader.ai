// Thin API client for the TubeMate Flask backend.

async function j(res) {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const b = await res.json()
      msg = b.error || msg
    } catch {}
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  authStatus: () => fetch('/api/auth/status').then(j),
  envDetected: () => fetch('/api/auth/env-detected').then(j),
  setup: (password, keys) => fetch('/api/auth/setup', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password, keys }),
  }).then(j),
  login: (password) => fetch('/api/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  }).then(j),
  // Exchange a verified Supabase access token for a local vault unlock.
  supabaseLogin: (access_token, keys) => fetch('/api/auth/supabase', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ access_token, keys: keys || {} }),
  }).then(j),
  logout: () => fetch('/api/auth/logout', { method: 'POST' }).then(j),
  reset: () => fetch('/api/auth/reset', { method: 'POST' }).then(j),
  adminStats: () => fetch('/api/admin/stats').then(j),
  adminFeedback: () => fetch('/api/admin/feedback').then(j),

  getKeys: () => fetch('/api/settings/keys').then(j),
  saveKeys: (keys) => fetch('/api/settings/keys', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(keys),
  }).then(j),

  getFixed: () => fetch('/api/settings/fixed').then(j),
  saveFixed: (fixed) => fetch('/api/settings/fixed', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fixed),
  }).then(j),

  channels: () => fetch('/api/channels').then(j),

  ytAccounts: () => fetch('/api/youtube/accounts').then(j),
  ytConnect: () => fetch('/api/youtube/connect', { method: 'POST' }).then(j),
  ytRemove: (id) => fetch(`/api/youtube/accounts/${id}`, { method: 'DELETE' }).then(j),
  ytSetProfile: (id, profile) => fetch(`/api/youtube/accounts/${id}/profile`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  }).then(j),

  drafts: () => fetch('/api/drafts').then(j),

  getDraft: (slug) => fetch(`/api/drafts/${slug}`).then(j),

  saveDraft: (slug, patch) =>
    fetch(`/api/drafts/${slug}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).then(j),

  generate: (form) => fetch('/api/generate', { method: 'POST', body: form }).then(j),

  resolveDrive: (input) =>
    fetch('/api/resolve-drive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input }),
    }).then(j),

  job: (id) => fetch(`/api/jobs/${id}`).then(j),

  jobs: () => fetch('/api/jobs').then(j),

  deleteDraft: (slug) => fetch(`/api/drafts/${slug}`, { method: 'DELETE' }).then(j),

  publish: (slug, patch) =>
    fetch(`/api/drafts/${slug}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch || {}),
    }).then(j),

  uploadThumb: (slug, file) => {
    const fd = new FormData()
    fd.append('thumbnail', file)
    return fetch(`/api/drafts/${slug}/thumbnail`, { method: 'POST', body: fd }).then(j)
  },

  thumbUrl: (slug) => `/api/drafts/${slug}/thumb?t=${Date.now()}`,
}

// Poll a job until it finishes; onTick(job) fires on each poll.
export function pollJob(id, onTick, interval = 1500) {
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const job = await api.job(id)
        onTick?.(job)
        if (job.status === 'done') return resolve(job)
        if (job.status === 'error') return reject(new Error(job.error || 'job failed'))
        setTimeout(tick, interval)
      } catch (e) {
        reject(e)
      }
    }
    tick()
  })
}
