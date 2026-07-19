// Supabase client for hosted Google auth + admin telemetry.
// Config comes from the backend (/api/config) so it isn't baked into the build.
import { createClient } from '@supabase/supabase-js'

let _client = null
let _initPromise = null

// Resolve the shared client (or null if Supabase isn't configured on this install).
export function getSupabase() {
  if (_client) return Promise.resolve(_client)
  if (!_initPromise) {
    _initPromise = fetch('/api/config')
      .then((r) => r.json())
      .then((cfg) => {
        if (!cfg.url || !cfg.anon_key) return null
        _client = createClient(cfg.url, cfg.anon_key, {
          auth: {
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: true, // completes the OAuth redirect back to the app
          },
        })
        return _client
      })
      .catch(() => null)
  }
  return _initPromise
}

// Kick off Google sign-in; Supabase brokers the flow and redirects back here.
export async function signInWithGoogle() {
  const sb = await getSupabase()
  if (!sb) throw new Error('Google sign-in is not configured.')
  const { error } = await sb.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin },
  })
  if (error) throw new Error(error.message)
}

export async function getSession() {
  const sb = await getSupabase()
  if (!sb) return null
  const { data } = await sb.auth.getSession()
  return data.session || null
}

export async function signOut() {
  const sb = await getSupabase()
  if (sb) await sb.auth.signOut().catch(() => {})
}

// Fire-and-forget telemetry. Metadata only — never content or keys. RLS ensures a
// user can only write their own rows.
export async function logEvent(type, extra = {}) {
  try {
    const sb = await getSupabase()
    if (!sb) return
    const { data } = await sb.auth.getSession()
    const uid = data.session?.user?.id
    if (!uid) return
    const { video_count = 1, model = null, ...meta } = extra
    await sb.from('usage_events').insert({
      user_id: uid, type, model, video_count, meta,
    })
  } catch {
    /* telemetry must never break the app */
  }
}
