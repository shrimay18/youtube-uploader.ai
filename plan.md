# TubeMate — YouTube Upload & SEO Automation Agent

> Personal pipeline to auto-generate SEO-heavy metadata and upload/schedule
> YouTube long-form + Shorts, with a human review gate. Built for ~10–12
> videos/month, $0 cost, no paid APIs.

**Status:** Code scaffolded + mechanically tested (2026-07-11). Pipeline runs
end-to-end except LLM call (needs GEMINI_API_KEY) and upload (needs OAuth). See
SETUP.md for the remaining human-only steps.
**Owner:** shrimaysomani18@gmail.com
**Last updated:** 2026-07-11

---

## 1. Problem statement
Creator + founder with no time for the manual upload chores. Want to hand the
agent a video (Drive link for long-form, local file for Shorts) and have it
produce a fully SEO-optimized, upload-ready draft — title, description, tags,
hashtags, chapters, category, pinned comment (+ Shorts thumbnail) — then upload
it instantly or at a scheduled time after a quick human approval.

- Frequency: 1–2/day, ~10–12/month.
- Constraint: student, free-tier tools only, no paid APIs.
- Goal: maximize discoverability/ranking, minimize clicks.

## 2. Key insights that shape the design
- **YouTube Data API v3 is free.** 10,000 quota units/day; an upload = 1,600
  units → ~6 uploads/day free. Never a bottleneck at our scale.
- **YouTube schedules natively.** Upload as `private` + `publishAt` timestamp →
  YouTube publishes itself. **No always-on server needed.** Laptop only needs to
  be on during `draft` and `publish`.
- **OAuth gotcha:** the `youtube.upload` scope is "sensitive." App in *Testing*
  mode = login token expires every 7 days. Fix: set OAuth consent to **"In
  production"**, bypass the unverified-app warning for your own account → token
  persists. One-time setup.
- **vidIQ has no free API** — it's a browser extension/dashboard only. Cannot be
  wired into the pipeline for free. Its keyword data is largely the same YouTube
  autocomplete we already pull. → Use it as an **optional manual gut-check at
  review time**, not in code.

## 3. End-to-end flow
```
  Google Drive link (long-form) ──┐
  + optional thumbnail (file/link)├──►  youtube_manager draft  ──►  draft.yaml + HTML preview
  Local file (Shorts) ────────────┘         │                        │
                                            │                YOU review / edit / approve
              transcribe · research · generate                       │
                                                                     ▼
                                                          youtube_manager publish draft.yaml
                                                                     │
                                                    upload private + publishAt
                                                                     ▼
                                              YouTube auto-publishes at chosen time (IST)
```
Two commands, one human checkpoint.

## 4. Pipeline stages
1. **Ingest** — Drive via `gdown` (file set to "anyone with link", no extra
   auth) OR a local path — **either source works for Shorts or long-form**.
   Format is auto-detected by duration (≤120s = Short, else long-form; override
   with `--short`/`--long`). Long-form accepts an **optional thumbnail** (local
   file OR link) so the draft is upload-ready.
2. **Understand** — extract audio (ffmpeg) → `faster-whisper` transcript **with
   timestamps** (local, free). Timestamps → auto-chapters.
3. **SEO research (free)** —
   - YouTube autocomplete (real search phrases)
   - Google Trends via `pytrends` (rising vs fading)
   - **Ranking signals** via YouTube Data API: top ~10 videos' **titles** (for the
     title flow) AND their **actual `snippet.tags`** (`videos.list` returns tags for
     any public video; `<meta name="keywords">` scrape as backup). Tags used across
     multiple top videos = proven ranking tags, fed into our tag generation.
   - Local **SEO scorer** (0-100) ranks each candidate title against this data.
   - NOTE: free signals give relevance + relative trend, **not** exact search
     volume (the paid feature we skip). Acceptable at our scale.
4. **Generate metadata (LLM, engine-agnostic)** —
   - **Title:** raw title from transcript → fetch top ~8 titles that currently
     *rank* for the topic (YouTube search) → writer drafts SEO titles from those
     patterns → judge scores the best, regenerates until it clears `min_score`.
     (Does NOT imitate the user's past titles — that pipeline was removed.)
   - **Body:** SEO description (keyword-rich first 2 lines + auto-chapters + links
     + CTA), tags, 3 hashtags, category, pinned-comment draft — written to match
     the final title. Driven by `channel_profile.yaml` (biggest quality lever, §6).
5. **Review gate** — writes `draft.yaml` (editable source of truth) + auto-opens
   an HTML preview. User picks/edits title, tweaks, sets `publish_at`. (Later:
   optional conversational review inside Claude Code.)
6. **Publish/schedule** — YouTube Data API v3 `videos.insert`, `private` +
   `publishAt` (RFC3339, **IST / Asia/Kolkata**). Instant = publish now.

### Thumbnails
- **Shorts:** auto-pick best frame (OpenCV scoring: sharpness + face presence +
  brightness) + optional bold text hook overlay (Pillow, LLM-generated phrase).
  Shown in preview; user can accept/skip/edit. Set via `thumbnails.set`.
- **Long-form:** user **optionally provides** their own thumbnail (file/link) at
  draft time → included in draft so it's upload-ready. No auto-generation for
  long-form (higher-stakes, designed deliberately).
- Requires channel to be phone-verified for custom thumbnails (confirm).

## 5. Architecture
```
youtube-upload-agent/
├─ plan.md                  # this file
├─ requirements.txt
├─ config/
│  ├─ channel_profile.yaml  # niche, tone, examples, banned words, links  (§6)
│  ├─ settings.yaml         # engine choice, timezone, defaults
│  └─ client_secret.json    # (gitignored) YouTube OAuth creds — user provides
├─ youtube_manager/
│  ├─ cli.py                # `draft` / `publish`
│  ├─ ingest.py             # gdown / local file + optional thumbnail
│  ├─ transcribe.py         # faster-whisper → transcript + timestamps
│  ├─ research.py           # YT autocomplete + pytrends + competitor scan
│  ├─ generate.py           # metadata via LLM
│  ├─ providers/            # gemini.py / ollama.py / claude.py (swappable)
│  ├─ frameselect.py        # OpenCV best-frame (Shorts)
│  ├─ thumbnail.py          # Pillow text overlay (Shorts)
│  ├─ review.py             # draft.yaml + HTML preview
│  └─ youtube.py            # OAuth + upload + schedule + thumbnail set
└─ drafts/                  # generated draft.yaml + previews per video
```
- **LLM behind one interface** → switch Gemini ↔ Ollama ↔ Claude via
  `settings.yaml`. Decide winner during build testing.

## 6. channel_profile.yaml (fill when we resume — TOP PRIORITY, drives quality)
```yaml
niche:        "???"           # <-- USER TO PROVIDE (e.g. founder vlogs / coding)
audience:     "???"           # <-- who watches
tone:         "???"           # <-- punchy / educational / raw
example_good_titles: []       # <-- past videos that did well (if any)
banned_words: []              # clickbait words to avoid
links:
  instagram:  ""
  website:    ""
  twitter:    ""
default_cta:  ""              # standard call-to-action for descriptions
```

## 7. Locked decisions
| # | Decision | Choice |
|---|----------|--------|
| A | Drive ingest | `gdown` + "anyone with link" (Drive OAuth later if needed) |
| B | channel_profile.yaml | YES — niche/tone TBD by user |
| C | Review mechanism | YAML file first; conversational-in-Claude later |
| D | Timezone | IST (Asia/Kolkata) |
| — | Shorts thumbnail | Auto frame-pick + optional text overlay |
| — | Long-form thumbnail | User-provided (optional) at draft time |
| — | vidIQ | Manual gut-check only, not in pipeline |
| — | LLM engine | Engine-agnostic; pick Gemini-free vs Ollama during build |

## 8. One-time setup the USER must do (I'll give exact click-steps)
1. Google Cloud project → enable **YouTube Data API v3** → create **OAuth
   Desktop** credentials → download `client_secret.json` → put in `config/`.
2. OAuth consent screen → **"In production"** (so login doesn't expire weekly).
3. Confirm channel is **phone-verified** (needed for custom thumbnails).
4. LLM engine: free **Gemini API key**, OR install **Ollama** locally.
5. Ensure **ffmpeg** installed (I'll verify; easy Windows install if missing).
   Python already installed. ✅

## 9. Deferred to v2+
Shorts auto-clipping from long-form · long-form auto-thumbnail · title/thumbnail
A/B testing · localized titles/descriptions · best-time-to-publish from
Analytics API · learning loop (feed CTR back into title generation) · caption
upload · conversational review in Claude · paid keyword-volume API (only if
monetizing).

## 10. Next steps when we resume
1. **USER:** fill niche + tone (for §6) — do this first, unblocks generation.
2. Verify ffmpeg; create venv + `requirements.txt`.
3. Scaffold repo structure (§5).
4. Build & test core pipeline: ingest → transcribe → research → generate →
   review (see AI output working before touching upload).
5. Do Google Cloud OAuth setup together (§8).
6. Build & test `youtube.py` upload + schedule on a throwaway private video.
7. Add Shorts frame-select + thumbnail overlay.
8. Dry-run one real long-form + one real Short end to end.
```
```
