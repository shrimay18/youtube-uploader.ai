"""YouTube — OAuth, upload, schedule, set thumbnail, pinned comment.

Uploads always go up as `private`; a `publishAt` (RFC3339) timestamp tells
YouTube to flip the video public itself at that moment — no server needed.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from dateutil import parser as dateparser
from dateutil import tz

from .util import fit_tags

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CLIENT_SECRET = CONFIG_DIR / "client_secret.json"


def _token_file(channel_key: str) -> Path:
    """Per-channel token so each channel stays logged in independently."""
    return CONFIG_DIR / f"token.{channel_key}.json"


def oauth_connect() -> str:
    """Run the loopback OAuth flow so the user can add a YouTube account.

    Opens the browser with the account chooser (so multiple accounts can be added),
    and returns the credentials as a JSON string to be stored encrypted by the caller.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow
    import os

    if not CLIENT_SECRET.exists():
        raise FileNotFoundError(
            f"Missing {CLIENT_SECRET}. Add your Google OAuth 'Desktop' client JSON there."
        )
    app_url = os.environ.get("TM_APP_URL", "http://127.0.0.1:8765/")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="select_account consent",  # always show the account chooser
        success_message=(
            "<!doctype html><meta charset='utf-8'><title>Account connected</title>"
            f"<meta http-equiv='refresh' content='0;url={app_url}'>"
            "<body style='font:15px system-ui;margin:18vh auto;max-width:420px;text-align:center;color:#111'>"
            "<div style='font-size:34px'>✅</div><h2 style='margin:.4em 0'>YouTube account connected</h2>"
            "<p style='color:#666'>Returning you to youtube_manager.ai…</p>"
            f"<script>location.replace({app_url!r})</script></body>"
        ),
    )
    return creds.to_json()


def service_from_token(token_json: str):
    """Build a YouTube client from a stored token JSON string (refreshing if needed)."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import json as _json

    creds = Credentials.from_authorized_user_info(_json.loads(token_json), SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds), creds


def channel_details(service) -> dict:
    """Return {id, title, handle, thumbnail} for the channel this token controls."""
    resp = service.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        return {"id": "", "title": "(no channel on this account)", "handle": "", "thumbnail": ""}
    it = items[0]
    sn = it.get("snippet", {})
    thumbs = sn.get("thumbnails", {})
    thumb = (thumbs.get("default") or thumbs.get("medium") or {}).get("url", "")
    return {
        "id": it["id"],
        "title": sn.get("title", ""),
        "handle": sn.get("customUrl", ""),
        "thumbnail": thumb,
    }


def get_service(channel_key: str = "default"):
    """Authenticate (browser flow first time) and return a YouTube API client.

    Each channel_key gets its own token file. On first login for a channel, pick
    that channel's Brand Account in the browser so the token controls the right one.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not CLIENT_SECRET.exists():
        raise FileNotFoundError(
            f"Missing {CLIENT_SECRET}. Create OAuth 'Desktop' credentials in Google "
            "Cloud (YouTube Data API v3 enabled), download the JSON, save it there."
        )

    token_file = _token_file(channel_key)
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print(
                f"\nAuthorizing channel '{channel_key}'. In the browser, pick the "
                "Google account/Brand Account for THIS channel."
            )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def channel_info(service) -> dict:
    """Return {'id','title'} of the channel the current token controls."""
    resp = service.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        return {"id": "", "title": "(no channel on this account)"}
    it = items[0]
    return {"id": it["id"], "title": it["snippet"]["title"]}


def _to_rfc3339_utc(publish_at: str, timezone: str) -> str:
    """Parse an IST-ish timestamp -> UTC RFC3339 with trailing Z (what the API wants)."""
    dt = dateparser.parse(publish_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.gettz(timezone))
    return dt.astimezone(tz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def upload(draft: dict, timezone: str = "Asia/Kolkata", progress=print,
           token_json: str | None = None) -> str:
    """Upload the video described by a draft dict. Returns the new video id.

    If token_json is given (a connected YouTube account), publish to that account;
    otherwise fall back to the legacy per-channel token file.
    """
    from googleapiclient.http import MediaFileUpload

    if token_json:
        service, _ = service_from_token(token_json)
        info = channel_details(service)
        progress(f"Target channel: {info['title'] or '(unknown)'}")
    else:
        channel_key = draft.get("_meta", {}).get("channel", "default")
        service = get_service(channel_key)
        # Confirm which channel this token actually controls (catches wrong-account logins).
        info = channel_info(service)
        progress(f"Target channel: {info['title']} (key: {channel_key})")

    video_path = draft["_meta"]["video_path"]
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file gone: {video_path}")

    publish_at = str(draft.get("publish_at", "")).strip().lower()
    privacy = str(draft.get("privacy", "private")).strip().lower()
    status: dict = {
        "selfDeclaredMadeForKids": bool(draft.get("made_for_kids", False)),
    }
    # Three modes:
    #   publish_at = "now"                    -> go public immediately
    #   publish_at empty/none/keep + private  -> upload and STAY private (manual publish later)
    #   publish_at = a future timestamp       -> upload private + auto-publish then (scheduled)
    if publish_at == "now":
        status["privacyStatus"] = "public"
    elif publish_at in ("", "none", "keep", "private", "unlisted"):
        status["privacyStatus"] = "unlisted" if privacy == "unlisted" else "private"
    else:
        status["privacyStatus"] = "private"
        status["publishAt"] = _to_rfc3339_utc(draft["publish_at"], timezone)

    tags = list(draft.get("tags", []))
    for h in draft.get("hashtags", []):
        tags.append(h.lstrip("#"))
    tags = fit_tags(tags, limit=500)      # YouTube caps total tag length at 500 chars

    snippet = {
        "title": draft["title"][:100],
        "description": draft.get("description", "")[:5000],
        "tags": tags,
        "categoryId": str(draft.get("category_id", "22")),
    }
    # Language: metadata language (we write English) + detected audio language.
    if draft.get("language"):
        snippet["defaultLanguage"] = str(draft["language"])
    if draft.get("audio_language"):
        snippet["defaultAudioLanguage"] = str(draft["audio_language"])

    body = {"snippet": snippet, "status": status}

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    progress("Uploading...")
    response = None
    while response is None:
        chunk_status, response = request.next_chunk()
        if chunk_status:
            progress(f"  {int(chunk_status.progress() * 100)}%")
    video_id = response["id"]
    progress(f"Uploaded: https://youtu.be/{video_id}")

    is_short = draft.get("_meta", {}).get("kind") == "short"
    thumb = str(draft.get("thumbnail", "")).strip()
    if thumb and Path(thumb).exists():
        try:
            set_thumbnail(service, video_id, Path(thumb))
            if is_short:
                progress("Thumbnail set (16:9, for search/suggested). NOTE: the vertical "
                         "Shorts-feed cover can't be set via API. Set it in YouTube Studio "
                         f"-> Edit -> Thumbnail. Image: {thumb}")
            else:
                progress("Thumbnail set.")
        except Exception as e:  # phone-verification / size issues shouldn't abort upload
            progress(f"  (thumbnail skipped: {e})")

    pinned = str(draft.get("pinned_comment", "")).strip()
    if pinned:
        try:
            post_pinned_comment(service, video_id, pinned)
            progress("Pinned comment posted.")
        except Exception as e:
            reason = "comments can't be posted on a PRIVATE video" if "403" in str(e) else str(e)
            progress(f"  (pinned comment not posted: {reason}; text saved in the draft, "
                     "post it once the video is public)")

    if "publishAt" in status:
        progress(f"Scheduled to go public at {draft['publish_at']} ({timezone}).")
    elif status["privacyStatus"] in ("private", "unlisted"):
        progress(f"Left as {status['privacyStatus']}. Publish it manually in YouTube Studio when ready.")
    return video_id


def set_thumbnail(service, video_id: str, image_path: Path) -> None:
    from googleapiclient.http import MediaFileUpload

    service.thumbnails().set(
        videoId=video_id, media_body=MediaFileUpload(str(image_path))
    ).execute()


def post_pinned_comment(service, video_id: str, text: str) -> None:
    # Insert a top-level comment as the channel owner. (True 'pin' is manual in
    # Studio; owner comments surface prominently and can be pinned in one click.)
    service.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": text}},
            }
        },
    ).execute()
