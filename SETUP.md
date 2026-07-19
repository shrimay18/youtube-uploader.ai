# TubeMate — one-time setup (things only YOU can do)

The code is built. These are the human-only steps. Do them once; after that it's
just `draft` and `publish`. Ordered by when you need them.

---

## ✅ Already done for you
- ffmpeg installed (v8.1.2).
- Python venv created at `.venv` with all dependencies.
- Full `youtube_manager/` pipeline scaffolded.

---

## 1. Name your two channels + fill each profile  ← DO THIS FIRST (biggest quality lever)

### 1a. Name the channels
Open `config/settings.yaml` → `channels:` block. Rename `label:` (and optionally
`handle:`) for `main` and `second` to your real channel names. `default_channel:`
is the one used when you don't pass `--channel`.

### 1b. Fill the profile(s)
Open `config/channel_profile.yaml` and replace every `???`. At minimum:
`niche`, `audience`, `tone`, `default_cta`. Add your links and any `banned_words`.

> Titles are NOT based on your past videos anymore. The agent writes a raw title
> from the transcript, pulls the top ~8 titles that currently *rank* for the
> topic, and generates an SEO title from those (with a judge that regenerates
> until it's good). That's what the `YOUTUBE_API_KEY` in step 3 powers.

**If your two channels are different niches/tones** (usually the case): copy
`channel_profile.yaml` to `channel_profile.second.yaml`, fill it for the 2nd
channel, and in `settings.yaml` set the `second` channel's `profile:` to that
file. If they're the same brand, leave both pointing at `channel_profile.yaml`.

*The metadata is only as good as these files. Two minutes here beats hours of editing later.*

---

## 2. Get a free Gemini API key (the LLM that writes metadata)
1. Go to **https://aistudio.google.com/apikey** (sign in with any Google account).
2. Click **Create API key** → copy it.
3. In PowerShell:
   ```powershell
   setx GEMINI_API_KEY "PASTE_YOUR_KEY_HERE"
   ```
4. **Close and reopen** the terminal (so the variable loads).

> **Fallback engines (automatic):** if Gemini's free daily quota runs out, the
> agent automatically falls through to **Groq** (free, fast — key `GROQ_API_KEY`
> from https://console.groq.com/keys) and then to **local Ollama** if installed.
> The chain is set by `engine` + `fallback` in `config/settings.yaml`. Prefer fully
> offline? Install Ollama (`ollama pull llama3.1:8b`, `ollama serve`) and it becomes
> the last-resort engine with no quota at all.

---

## 2b. Get a free YouTube Data API key (powers the ranking-title search)
This is what lets the agent pull the top titles that currently *rank* for your
topic and build a proper SEO title from them. Without it, drafts still work but
skip that optimization.

1. Go to **https://console.cloud.google.com/** → create/select a project
   (you'll reuse this same project for step 3).
2. Search **YouTube Data API v3** → **Enable**.
3. **APIs & Services** → **Credentials** → **+ Create Credentials** → **API key**
   → copy it.
4. In PowerShell:
   ```powershell
   setx YOUTUBE_API_KEY "PASTE_YOUR_KEY_HERE"
   ```
5. **Close and reopen** the terminal.

*(This is a plain API key — different from the OAuth `client_secret.json` in
step 3. One search per draft ≈ 100 of your 10,000 free daily units.)*

At this point you can run a full **draft** (steps 1, 2, 2b are all `draft` needs).

---

## 3. YouTube upload access (needed only for `publish`)

### 3a. Create a Google Cloud project + enable the API
1. Go to **https://console.cloud.google.com/** → top bar → **Select a project** →
   **New Project** → name it `youtube_manager` → **Create**.
2. Search bar → **YouTube Data API v3** → **Enable**.

### 3b. OAuth consent screen → set to Production (so login doesn't expire weekly)
1. Left menu → **APIs & Services** → **OAuth consent screen**.
2. User type **External** → **Create**.
3. Fill App name (`TubeMate`), your email for both support + developer contact →
   **Save and Continue** through the screens.
4. Back on the OAuth overview, under **Publishing status** click
   **Publish App** → confirm. Status should read **In production**.
   *(Ignore the "verification" prompt — it only matters for public apps; for your
   own account you'll just click through a one-time "unverified" warning.)*

### 3c. Create OAuth **Desktop** credentials
1. **APIs & Services** → **Credentials** → **+ Create Credentials** →
   **OAuth client ID**.
2. Application type: **Desktop app** → name it → **Create**.
3. **Download JSON** → rename to `client_secret.json` → put it in this repo's
   `config/` folder (i.e. `config/client_secret.json`).

### 3d. Authorize EACH channel (one login per channel)
Both channels use the same `client_secret.json`, but each gets its own saved
login token. Authorize them up front:

```powershell
python -m youtube_manager auth --channel main
python -m youtube_manager auth --channel second
```

Each opens a browser. Sign in / **pick the Brand Account for THAT channel**, click
through the "unverified app" warning (**Advanced → Go to TubeMate**), and allow.
The command then prints *which channel the token actually controls* — check it
matches. Tokens are saved as `config/token.main.json` / `config/token.second.json`,
so you won't be asked again.

> Two channels under one Google login = "Brand Accounts". The account picker in
> the browser is where you choose which one each token points at. If you pick the
> wrong one, delete that `token.<key>.json` and re-run `auth`.

Check status anytime: `python -m youtube_manager channels`

---

## 4. Confirm channel is phone-verified (for custom thumbnails)
**https://www.youtube.com/verify** — needed to set custom thumbnails
(both your long-form uploads and the auto-generated Shorts thumbnail). If it's
not verified, uploads still work; only the thumbnail step is skipped.

---

## What I still need from you to finish testing
1. **channel_profile.yaml filled** (step 1) + **GEMINI_API_KEY set** (step 2)
   → then I can run a real end-to-end **draft** on a sample video and show you output.
2. A **sample video** to test on — either a Drive link (long-form) or a small
   local `.mp4` (Short). A 30–60s clip is perfect for a first dry run.
3. When you're ready to test **publish**: `client_secret.json` in `config/`
   (step 3). We'll first publish to a throwaway **private** video to verify.
