# P1 — Server-side key storage + per-request JWT auth (multi-tenant)

**Goal:** replace the on-device vault (local file + OS keychain + in-memory `_STATE` +
keys pushed to `os.environ`) with **per-user encrypted storage in Supabase** and
**stateless per-request auth**, so one hosted backend can safely serve many users.
This also removes the global mutable state (the DIP smell) — `os.environ` key stuffing
is a correctness bug under multi-tenant concurrency, not just a style issue.

---

## 1. Data model (Supabase)

```sql
create table public.user_keys (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  provider      text not null,          -- 'anthropic'|'gemini'|'openai'|'groq'|'custom'
  label         text,                   -- display name for custom providers
  model         text,                   -- optional (custom / override)
  base_url      text,                   -- custom OpenAI-compatible base
  key_ciphertext text not null,         -- Fernet(TM_MASTER_KEY, api_key)
  position      int not null default 0, -- ordering within a provider
  created_at    timestamptz not null default now()
);
create index on public.user_keys(user_id, position);
alter table public.user_keys enable row level security;
-- NO policies on purpose: only the backend service_role (bypasses RLS) reads/writes.
-- The public anon/authenticated keys can NEVER read a key row, and even a leak only
-- exposes ciphertext (undecryptable without the backend master key).

create table public.user_prefs (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  engine_order text[] not null default '{}',  -- provider order tokens
  updated_at   timestamptz not null default now()
);
alter table public.user_prefs enable row level security;  -- backend-only, same as above
```

Keys are **never** exposed to the browser: the frontend calls the backend, which
returns only **masked** views (first6…last4) — identical to today's `masked_config()`.

---

## 2. Encryption

- Backend env `TM_MASTER_KEY` = a urlsafe-base64 Fernet key (host secret, never shipped).
- `encrypt(k) = Fernet(TM_MASTER_KEY).encrypt(k)`; `decrypt(c) = …decrypt(c)`.
  Reuse the exact Fernet logic already in `vault.py`.
- **Beta:** one master key for all users (simple, fast).
- **Later:** envelope encryption (per-user data key wrapped by the master/KMS) so a
  single key rotation doesn't touch every row.

---

## 3. Auth — per request, stateless (replaces the single-user guard)

```python
@app.before_request
def authenticate():
    p = request.path
    if p in OPEN or not p.startswith("/api/"):
        return
    claims = supabase_auth.verify(bearer_token(request))   # existing JWKS/ES256 verify
    if not claims:
        return jsonify({"error": "auth required"}), 401
    g.user = UserContext(id=claims["sub"], email=claims.get("email"))
```

- Frontend attaches `Authorization: Bearer <supabase access_token>` to every `/api` call
  (it already holds the Supabase session).
- `g.user` is **request-scoped** (`flask.g`) — no module-level globals, no `_STATE`.

---

## 4. Service layer (replaces `vault`)

`KeyService` (backend; Supabase service role + master key):

| method | replaces (today) |
|---|---|
| `list_masked(user_id)` | `vault.masked_config()` |
| `save(user_id, ops, custom, order)` | `vault.save_config()` |
| `keys_for(user_id, provider)` | `vault.llm_keys()` |
| `custom_providers(user_id)` | `vault.custom_providers()` |
| `engine_order(user_id)` | `vault.engine_order()` |
| `has_any(user_id)` | `vault.has_llm_key()` |

`get_provider(ctx)` builds the `FallbackProvider` from **`ctx`** (a per-request
`UserContext`) instead of the global vault. The `KeyedProvider` / `FallbackProvider` /
rotation logic is **unchanged and already unit-tested** — only the *source* of keys moves.

---

## 5. Endpoints — same shape, now per-user

- `GET  /api/settings/keys`  → `KeyService.list_masked(g.user.id)`
- `POST /api/settings/keys`  → `KeyService.save(g.user.id, …)`
- generate / publish / accounts → resolve keys via `get_provider(build_ctx(g.user))`.

Response contracts stay identical, so the **frontend needs almost no change** beyond
sending the `Authorization` header.

---

## 6. What changes / is removed

- `vault.py` local model (account.json, keyring, `_STATE`, `os.environ`) → gone for the
  hosted path (keep only a thin local-dev shim if we still want a desktop build).
- `_activate()` pushing keys into `os.environ` → **deleted** (unsafe across concurrent
  users; keys now flow through `ctx` explicitly).
- `webapp.before_request` single-user guard → JWT verification above.

---

## 7. Sequence

```
Browser (Supabase JWT)
   │  GET /api/settings/keys   Authorization: Bearer <jwt>
   ▼
Backend  ── verify JWT ──▶ g.user
         ── KeyService.list_masked(uid)
              └─ Supabase(service_role): select * from user_keys where user_id = uid
              └─ decrypt(TM_MASTER_KEY) → mask (first6…last4)
         ◀── JSON (masked)
```

---

## 8. Rollout

1. Run the `user_keys` + `user_prefs` migration in Supabase.
2. Set `TM_MASTER_KEY` on the backend host.
3. Land `KeyService` + JWT middleware behind a flag; keep the local vault for dev.
4. Frontend: attach the `Authorization` header (session already available).

## Open decisions (need your call)
- **Backend host:** Render / Railway / Fly? (Not Vercel.)
- **Encryption:** single master key (recommended for beta) vs per-user envelope (later)?
