# YouTube API Services — Audit & Quota Extension: application pack

Paste/adapt these answers into the audit form. Fill the `[…]` placeholders.

## App summary
**youtube_manager.ai** is a web app that helps creators turn a video into a
publish-ready, SEO-optimized YouTube post and publish/schedule it to channels they own.
Users sign in with Google, connect their own YouTube channel(s) via OAuth, and the app
writes the title, description, tags, chapters and thumbnail, then uploads on their behalf.

## OAuth scope requested & justification
- `https://www.googleapis.com/auth/youtube.force-ssl` (restricted). Needed to, **on
  channels the user explicitly connects**: upload videos, set their title/description/
  tags/category/thumbnail, set privacy & scheduled-publish time, verify the connected
  channel, and (optionally) post a pinned comment the user wrote. We request nothing
  beyond what these features require.

## API methods used
| Method | Purpose | Units |
|---|---|---|
| `search.list` | find top-ranking videos for the topic (SEO research) | 100 |
| `videos.list` | read public titles/tags of those videos + verify uploads | 1 |
| `videos.insert` | upload the user's video | 1600 |
| `thumbnails.set` | set the thumbnail | ~50 |
| `videos.update` | set/adjust snippet + status (schedule/privacy) | ~50 |
| `commentThreads.insert` | optional pinned comment | ~50 |
| `channels.list` | confirm the connected channel owns the upload | 1 |

## Quota justification (do the math in the form)
- One full publish ≈ `1600 + 50 + 50 (+50 optional)` ≈ **~1,750 units**.
- One research pass ≈ `100 + 1` ≈ **~101 units** per draft.
- To support **[N] uploads/day**: e.g. 100/day ⇒ `100 × 1,750 = 175,000` + research ≈
  **~185,000/day** → request **250,000/day** for headroom.
- The default **10,000/day supports only ~6 uploads across ALL users combined** — far
  short of a multi-user service. State this explicitly.

## Compliance checklist (owner)
- [x] Privacy Policy exists + links to YouTube ToS & Google Privacy Policy (in `Legal.jsx`).
- [x] Limited Use / Google API Services User Data Policy disclosure present.
- [x] Users can disconnect a channel and revoke access (Google permissions link present).
- [ ] **Privacy policy rewritten for the HOSTED model** — see the ⚠️ below. **(blocker)**
- [ ] Demo video of the full flow. **(you)**
- [ ] OAuth app verified (restricted scope ⇒ verification, possibly a security
      assessment). **(you)**
- [ ] App publicly reachable so the reviewer can test it. **(after P4 hosting)**

## ⚠️ The privacy policy MUST be rewritten before submitting
The current policy says data *"stays on your device / never reaches us."* That is true for
the local app but **false once hosted** — keys, YouTube tokens and videos will live
(encrypted) on your server. Reviewers verify the policy matches real behavior; a mismatch
is a rejection **and** a misrepresentation. The SaaS-accurate policy must state: we store
your API keys and YouTube tokens **encrypted on our servers (Supabase)**, process your
videos on our servers, delete source files after processing, and never sell/serve-ads-on
Google user data (Limited Use). Do this as part of P4, matching the deployed behavior,
**then** submit.

## Demo video script (~2–3 min)
1. Landing → Get started → Google sign-in.
2. Add an AI key (or note bring-your-own) → connect a YouTube channel (OAuth consent).
3. Paste a Drive link / upload → Generate → show the SEO title/tags/thumbnail.
4. Publish or schedule (use private/unlisted for the demo) → show it on the channel.
5. Show Disconnect / how to revoke access at myaccount.google.com/permissions.
