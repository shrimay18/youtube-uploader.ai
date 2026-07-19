# Google OAuth verification — checklist & copy

Everything you need to submit youtube_manager.ai for Google OAuth verification so the
"Google hasn't verified this app" screen disappears for all users.

## 0. Before you submit — replace these placeholders

The site is ready except for a few things only you can set:

- **Contact email**: the pages use `support@youtube-manager.ai`. Change it to a mailbox
  you actually monitor (Google emails this address during review). Find/replace it in
  `index.html`, `privacy.html`, `terms.html`. A working address is required.
- **Domain**: pick the real domain you'll register (e.g. `youtube-manager.ai` or
  `youtubemanager.ai`) and use it consistently below. Update the email domain to match.

## 1. Deploy the site (Vercel)

1. Push this `site/` folder to a Git repo (or `vercel deploy` it directly).
2. In Vercel, add your **custom domain** to the project.
3. Confirm these load publicly (no login):
   - `https://<your-domain>/`         → homepage
   - `https://<your-domain>/privacy`  → privacy policy
   - `https://<your-domain>/terms`    → terms
   (`cleanUrls` in vercel.json makes the `.html` optional.)

## 2. Verify domain ownership

- Add and verify your domain in **Google Search Console**
  (https://search.google.com/search-console) using the DNS TXT record method —
  add the TXT record in Vercel → Domains → DNS.
- Use the **same Google account** that owns the Cloud project (`shrimaytwin`).

## 3. Configure the OAuth consent screen

Google Cloud Console → APIs & Services → OAuth consent screen:

- **App name**: youtube_manager.ai
- **User support email**: your monitored address
- **App logo**: upload a square logo (≥120×120 PNG)
- **App homepage**: `https://<your-domain>/`
- **Privacy policy URL**: `https://<your-domain>/privacy`
- **Terms of service URL**: `https://<your-domain>/terms`
- **Authorized domains**: add `<your-domain>` (the naked domain, no https)
- **Developer contact email**: your address
- Publishing status: **In production**

## 4. Scopes — paste this justification

**Scope requested:** `https://www.googleapis.com/auth/youtube.force-ssl`

**Why this scope (paste into the justification box):**

> youtube_manager.ai lets a creator upload their own videos to their own YouTube
> channel(s) and set the video's metadata. We use youtube.force-ssl to, on channels the
> user explicitly connects: (1) upload videos the user selects (videos.insert);
> (2) set title, description, tags, category and thumbnail (thumbnails.set);
> (3) set privacy status or a scheduled publish time; and (4) optionally post a pinned
> comment the user has written (commentThreads.insert). Posting the user's comment
> requires youtube.force-ssl rather than the narrower youtube.upload scope. We do not
> read or analyze other users' data. Tokens are stored encrypted on the user's own
> device and requests are made directly from that device.

**Scope-minimization note (your decision):** if you drop the *pinned-comment* feature,
you can switch to the narrower **`youtube.upload`** scope (upload + thumbnail + status),
which is easier to get verified. force-ssl is only needed because we post comments.

## 5. Demo video (required for sensitive scopes)

Record a short (2–4 min) screen recording, upload to YouTube (unlisted is fine), and
paste the link in the verification form. Show, in order:

1. Your live site at `https://<your-domain>/` and the privacy policy page.
2. Opening youtube_manager.ai and clicking **Connect a YouTube account**.
3. The **Google OAuth consent screen** — clearly show the app name and the
   youtube.force-ssl permission being granted.
4. Back in the app: generating a draft and **publishing a video** to the connected
   channel (this demonstrates the scope actually being used for its stated purpose).
5. Briefly show that keys/tokens are entered/stored in the app on the device.

## 6. Submit & wait

Submit for verification. Google typically replies in a few days to a few weeks and may
ask follow-up questions — answer from the developer contact email. Sensitive scopes
(YouTube) do **not** require the third-party security assessment that restricted scopes
(Gmail/Drive) do, so this is the lighter path.

## While you wait

The app still works — users just see the "unverified app → Advanced → Continue" screen.
A clean app name + logo + these live policy links already make that screen look far more
legitimate. Verified status removes the screen entirely.
