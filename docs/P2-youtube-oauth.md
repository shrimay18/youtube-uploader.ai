# P2 — Hosted YouTube OAuth + shared→BYO upload routing

**Built + tested** (`oauth.py`, `oauthclients.py`, `channelstore.py`, `uploadrouting.py`,
migration `0004`). This doc covers the **live Flask routes + BYO wizard** that need the
hosted redirect URI (done at deploy, alongside P1 integration).

## Connect flow (web OAuth, replaces loopback)
```
POST /api/youtube/oauth/start   { kind: 'app' | 'user' }
  → pick the client: app = app_client() (env);  user = user_client(store,crypto,uid)
  → state = signed({uid, kind, nonce})
  → return oauth.build_auth_url(client_id, REDIRECT_URI, state)   # frontend redirects

GET  /api/youtube/oauth/callback?code=…&state=…
  → verify state (uid, kind)
  → tokens = oauth.exchange_code(client_id, client_secret, REDIRECT_URI, code)
  → identify channel: youtube.channels.list(mine=true) with tokens.access_token
  → channelstore.upsert({user_id, channel_id, client_kind: kind, title, handle,
                         thumbnail, refresh_token_ciphertext: crypto.enc(tokens.refresh_token)})
  → redirect back to the app
```
`REDIRECT_URI` = `https://<backend-host>/api/youtube/oauth/callback` — must be added to the
OAuth client's "Authorized redirect URIs" in Google Cloud (for BOTH the app client and, in
the wizard instructions, the user's own client).

## BYO-client wizard (`kind='user'`)
Guided steps in the UI, then:
```
POST /api/youtube/client   { client_id, client_secret }
  → oauthclients.save_user_client(store, crypto, uid, client_id, client_secret)   # secret encrypted
```
Wizard copy: create a Google Cloud project → enable YouTube Data API v3 → create an OAuth
**client (Web application)** → add our redirect URI → paste `client_id` + `client_secret`.
After saving, they run the connect flow with `kind='user'`.

## Upload routing (the product decision)
At publish time, for a channel, gather its connections and route:
```python
conns = channelstore.list_for(uid)  # rows for that channel_id
mode  = 'bulk' if bulk else 'single'
def do_upload(conn):
    client = app_client() if conn['client_kind']=='app' else user_client(store,crypto,uid)
    access = oauth.refresh_access_token(client.client_id, client.client_secret,
                                        crypto.dec(conn['refresh_token_ciphertext']))['access_token']
    return youtube.upload(draft, access_token=access, …)   # 403 quota → raise QuotaExceeded
run_with_quota_fallback(conns, mode, do_upload)
```
- **single:** app first → on `QuotaExceeded` → user's own. If none left → prompt "add your own credentials."
- **bulk:** user's own only; if none → `NoCredentials` → prompt the wizard.

`youtube.upload` needs a small change: accept an `access_token` (from the routed client)
instead of building creds from a local `client_secret.json`, and raise `QuotaExceeded` on a
403 `quotaExceeded` from `videos.insert`.

## Integration checklist (at deploy)
1. Run migration `0004_youtube_oauth.sql`.
2. Set env: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (app client), `TM_MASTER_KEY`.
3. Add `…/api/youtube/oauth/callback` to the app client's redirect URIs.
4. Add the routes above; switch `accounts.py` reads/writes to `SupabaseChannelStore`.
5. Frontend: "Connect a YouTube channel" → `oauth/start`; add the BYO wizard; bulk setup
   requires a `user` connection.
6. `youtube.upload(access_token=…)` + `QuotaExceeded` on 403.
```
