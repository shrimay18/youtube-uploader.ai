# P4 — Deploy runbook (Oracle Always-Free VM + Vercel)

Two parts: **(A) infra** (this runbook — you run it on your Oracle account) and
**(B) code integration** (wiring P1–P3 into live routes — the checklist at the bottom;
best done here against live Supabase so it's testable).

Architecture: **Vercel** (React) → HTTPS → **Oracle VM** (gunicorn + rq worker + Redis +
ffmpeg) → **Supabase** (Postgres, encrypted keys/tokens, telemetry).

---

## A. Oracle VM

### 1. Create the VM
- Oracle Cloud → Compute → Instances → Create.
- Shape: **Ampere A1 (VM.Standard.A1.Flex)**, e.g. **2 OCPU / 12 GB** (Always-Free allows up to 4/24).
- Image: **Ubuntu 22.04**. Download the SSH key.
- Networking → allow **80** and **443** (Ingress rules in the VCN security list), plus 22.

### 2. Base packages
```bash
ssh ubuntu@<vm-public-ip>
sudo apt update && sudo apt install -y python3-venv python3-pip ffmpeg redis-server git caddy
sudo systemctl enable --now redis-server
```

### 3. App + deps
```bash
git clone <your-repo> app && cd app
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-prod.txt
python -m pytest -q            # sanity: should be green
```

### 4. Supabase migrations
In the Supabase SQL editor, run (once, in order):
`0002_feedback.sql`, `0003_user_keys.sql`, `0004_youtube_oauth.sql`.

### 5. Backend env (`app/.env` — gitignored)
```bash
# generate the master key ONCE and keep it safe:
python -c "from youtube_manager.keycrypto import KeyCrypto; print(KeyCrypto.generate_master_key())"
```
```
TM_MASTER_KEY=<the value above>
SUPABASE_URL=https://vjfxmsfmyeiogeghmzrx.supabase.co
SUPABASE_ANON_KEY=<anon key>
SUPABASE_SERVICE_KEY=<service key>          # backend only
GOOGLE_CLIENT_ID=<app oauth client id>
GOOGLE_CLIENT_SECRET=<app oauth client secret>
YOUTUBE_API_KEY=<key1>,<key2>,<key3>        # research (rotated)
REDIS_URL=redis://localhost:6379
TM_TRANSCRIBER=local                        # or 'deepgram'/'openai' (+ its key)
DEEPGRAM_API_KEY=...                        # if TM_TRANSCRIBER=deepgram
TM_ALLOWED_ORIGIN=https://<your-app>.vercel.app
TM_APP_URL=https://api.<your-domain>
# App-level LLM keys (your beta pool): GEMINI_API_KEY / GROQ_API_KEY / ...
```

### 6. systemd services
`/etc/systemd/system/ytm-web.service`
```ini
[Unit]
Description=youtube_manager web
After=network.target redis-server.service
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
EnvironmentFile=/home/ubuntu/app/.env
ExecStart=/home/ubuntu/app/.venv/bin/gunicorn -w 2 -k gthread --threads 8 --timeout 120 -b 127.0.0.1:8765 wsgi:app
Restart=always
[Install]
WantedBy=multi-user.target
```
`/etc/systemd/system/ytm-worker.service`
```ini
[Unit]
Description=youtube_manager worker
After=network.target redis-server.service
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/app
EnvironmentFile=/home/ubuntu/app/.env
ExecStart=/home/ubuntu/app/.venv/bin/python worker.py
Restart=always
[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ytm-web ytm-worker
```

### 7. HTTPS (Caddy auto-TLS)
Point DNS `api.<your-domain>` → the VM's public IP. `/etc/caddy/Caddyfile`:
```
api.<your-domain> {
    reverse_proxy 127.0.0.1:8765
}
```
```bash
sudo systemctl restart caddy
```

---

## B. Vercel frontend
- Import the `frontend/` project on Vercel.
- Env var: `VITE_API_URL=https://api.<your-domain>` (the frontend calls this + sends the Supabase JWT).
- Deploy → you get `https://<your-app>.vercel.app` (put it in `TM_ALLOWED_ORIGIN`).

## Google Cloud
- OAuth client (Web) → **Authorized redirect URI:** `https://api.<your-domain>/api/youtube/oauth/callback`.
- Add your Vercel domain to the OAuth consent screen's authorized domains.
- Add beta users as **test users** (unverified app cap = 100) while the audit/verification is in flight.

---

## Remaining code integration (part B — do here, test against live Supabase)
Modules are built + tested; these wire them into live routes:
1. **Auth:** in `webapp.create_app`, add a `before_request` (when `TM_MODE=saas`) using
   `auth_web.context_from_request(request, key_service)` → `g.user`; instantiate
   `KeyService(SupabaseKeyStore(...), KeyCrypto.from_env())`.
2. **Keys:** point `/api/settings/keys` GET/POST at `key_service.list_masked/save(g.user.id)`.
3. **Provider:** swap `get_provider(settings)` → `get_provider_for(g.user_ctx, settings)`.
4. **YouTube OAuth:** add `/api/youtube/oauth/start` + `/callback` + `/client` (see
   `docs/P2-youtube-oauth.md`); switch `accounts` to `SupabaseChannelStore`; route uploads
   through `uploadrouting.run_with_quota_fallback`.
5. **Jobs:** replace `_JOBS`/threads with `get_job_queue()`; `/api/jobs` reads it.
6. **Transcription:** `pipeline` extract-audio-once → `get_transcriber(settings).transcribe(audio)`.
7. **Frontend:** `api.js` prefix `VITE_API_URL` + send `Authorization: Bearer <supabase jwt>`.
8. **Video handling:** download/upload to a temp dir (or object storage), delete in `finally`.
