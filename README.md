# youtube_manager.ai

AI YouTube Manager — turns a raw video into an SEO-optimized, upload-ready
YouTube draft, then uploads/schedules it after a one-click human review.
(Internal package/CLI is still `youtube_manager`.)

See [plan.md](plan.md) for the full design. Two commands, one review gate.

## Quickstart

### Web app (recommended)

```powershell
.\.venv\Scripts\Activate.ps1
python -m youtube_manager serve          # opens the React studio at http://127.0.0.1:8765
```

A premium web UI: pick a channel, drop a video or paste a Drive link, watch it
generate, then edit every field (scored titles, description, tags, thumbnail,
compliance, publish mode) and publish — all in the browser. Dark/light themes.

First-time frontend build (once): `npm --prefix frontend install && npm --prefix frontend run build`
(the built `frontend/dist` is committed, so this is only needed if you change the UI).

### CLI

```powershell
# 1. Activate the venv
.\.venv\Scripts\Activate.ps1

# 2. Name your channels in config/settings.yaml + fill config/channel_profile.yaml
# 3. Set your LLM key (free Gemini):        setx GEMINI_API_KEY "your-key"

# 4. See your configured channels + auth status
python -m youtube_manager channels

# 5. Draft a video — Drive link OR local file; Short vs long-form is auto-detected by length
python -m youtube_manager draft "https://drive.google.com/file/d/<ID>/view" --channel shrimay
python -m youtube_manager draft "C:\path\myvideo.mp4" --channel delta

#   Optional: force the format, or add a long-form thumbnail
python -m youtube_manager draft "<source>" --channel delta --short
python -m youtube_manager draft "<source>" --channel shrimay --thumbnail "C:\path\thumb.png"

# 6. Review & edit in the browser, then Save + Publish right there (recommended)
python -m youtube_manager review drafts/<slug>.yaml

#   …or edit drafts/<slug>.yaml by hand and publish from the CLI:
python -m youtube_manager publish drafts/<slug>.yaml
python -m youtube_manager publish drafts/<slug>.yaml --channel delta   # override channel
```

**Multiple channels:** each `--channel <key>` targets a channel defined in
`config/settings.yaml`. Authorize each once with `python -m youtube_manager auth --channel <key>`
(picks the right Brand Account in the browser). Omit `--channel` to use the
`default_channel`. Each channel can have its own SEO/tone profile.

## What each command does

- **Source & format:** a video can come from a **Google Drive link or a local
  file**, and TubeMate auto-classifies it as a **Short** (≤ `short_max_seconds`,
  default 120s) or **long-form** by its actual duration. Override with `--short`/`--long`.
- **draft** — ingest (gdown/local) → transcribe (faster-whisper) → SEO research
  (YouTube autocomplete + Google Trends) → generate metadata (LLM) →
  Shorts thumbnail (best-frame + text overlay) → write `draft.yaml` + HTML preview.
  - **Title flow:** the agent pulls the top ~10 ranking videos for the topic → the
    model writes 7 candidate titles learning those winning patterns → a local SEO
    scorer (0-100, tuned to the ranking data) scores each; the best is chosen and
    regenerated if it's below `title.min_seo_score`. The review UI shows every title
    with its score.
  - **Tags from real competitors:** it reads the *actual* `snippet.tags` of the top
    ranking videos (YouTube Data API `videos.list`; `<meta name="keywords">` scrape
    as backup), keeps the ones used across multiple top videos (proven ranking tags),
    blends in your video's specifics, and packs to 450-500 chars.
- **review** — opens an editable page at `localhost`: edit title/description/tags/
  thumbnail/publish-mode, **Save** writes back to `draft.yaml`, **Publish** uploads
  with those exact edits. (Tag box shows a live 0/500-char counter.)
- **publish** — reads the reviewed `draft.yaml` and uploads. Publish modes:
  `publish_at: now` → public immediately; empty/`none` → upload and **stay private**
  (publish manually later); a future IST timestamp → private + auto-publish then.

> **Gemini free tier** is ~20 requests/day; each draft uses ~3, so ~6 drafts/day.
> If you hit the cap, wait for the daily reset (~1:30 PM IST) or switch
> `engine: ollama` in settings for unlimited local generation.

## Switching niche / target audience

The profile file is read fresh every run and is the only thing that shapes the
model's output — so adapting is just editing config.

- **Permanent switch:** edit the channel's profile file — update `niche`,
  `audience`, `tone`, **and clear/replace `example_good_titles` + `banned_words`**
  (old titles make the model imitate the old niche). Every draft after that adapts.
- **Test-drive a new direction / one-off video:** don't touch your live profile —
  make a new file (e.g. `config/channel_profile.newniche.yaml`) and run a single
  draft against it with `--profile`:
  ```powershell
  python -m youtube_manager draft --short "clip.mp4" --profile channel_profile.newniche.yaml
  ```
  A bare filename resolves under `config/`; a full path also works. Great for
  A/B-ing old vs new niche before you commit.

## Configuration

- `config/settings.yaml` — LLM engine (`gemini`/`ollama`/`claude`), timezone,
  Whisper model, research toggles.
- `config/channel_profile.yaml` — niche, tone, links, CTA. **Fill this first.**
- `config/client_secret.json` — YouTube OAuth creds (you provide; see plan §8).

## Environment variables

| Var | Needed for | How to get |
|-----|-----------|-----------|
| `GEMINI_API_KEY` | metadata generation (default engine) | https://aistudio.google.com/apikey (free) |
| `YOUTUBE_API_KEY` | ranking-title search (the SEO title flow) | Google Cloud → API key (free) |
| `ANTHROPIC_API_KEY` | only if `engine: claude` | https://console.anthropic.com |

Set on Windows: `setx GEMINI_API_KEY "your-key"` then reopen the terminal.
