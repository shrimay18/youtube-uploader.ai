"""TubeMate CLI — two commands: draft and publish.

  python -m youtube_manager draft --long  <drive-link> [--thumbnail path|link] [--slug name]
  python -m youtube_manager draft --short <local-file> [--slug name]
  python -m youtube_manager publish drafts/<slug>.yaml

draft  = ingest -> transcribe -> research -> generate -> (thumbnail) -> review
publish = read draft.yaml -> upload private + publishAt (or now)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml

from . import config
from . import pipeline


def cmd_draft(args) -> int:
    settings = config.settings()

    try:
        channel_key = config.resolve_channel(args.channel)
    except ValueError as e:
        print(e)
        return 2
    label = config.channel_label(channel_key)
    print(f"Channel: {label} (key: {channel_key})")

    # --profile overrides the channel's saved profile for this one draft.
    if args.profile:
        profile = config.load_profile_override(args.profile)
        missing = config.check_profile(profile)
        profile_src = args.profile
        print(f"Using override profile: {args.profile}")
    else:
        profile = config.channel_profile(channel_key)
        missing = config.check_profile(profile)
        profile_src = str(config._profile_path(channel_key))

    if missing:
        print(f"Profile is incomplete. Fill these before drafting: {', '.join(missing)}")
        print(f"\nEdit: {profile_src}")
        return 2

    source = args.source
    slug = args.slug or pipeline.slugify(
        Path(source).stem if not source.startswith("http") else "video"
    )
    force = "short" if args.short else ("long" if args.long else None)

    from .providers.base import QuotaExceeded
    try:
        result = pipeline.build_draft(
            settings, profile, source, channel_key, label, slug,
            thumbnail=args.thumbnail, force_kind=force, log=print,
        )
    except QuotaExceeded as e:
        print(f"\nAborted — {e}")
        print("(No draft written. Your transcript is cached, so re-running later is fast.)")
        return 1

    draft_path = result.draft_path
    print(f"\nDraft ready: {draft_path}")
    if args.no_review:
        print("Edit it in the browser, then Save + Publish there:")
        print(f"  python -m youtube_manager review {draft_path.relative_to(config.ROOT)}")
        print("Or edit the YAML directly and:")
        print(f"  python -m youtube_manager publish {draft_path.relative_to(config.ROOT)}")
        return 0

    # Open the single (editable) review UI directly.
    from . import reviewserver
    reviewserver.serve(draft_path, settings, open_browser=True)
    return 0


def cmd_publish(args) -> int:
    settings = config.settings()
    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"Draft not found: {draft_path}")
        return 2
    with draft_path.open("r", encoding="utf-8") as fh:
        draft = yaml.safe_load(fh)

    # --channel overrides the channel recorded in the draft, if given.
    if args.channel:
        try:
            ch = config.resolve_channel(args.channel)
        except ValueError as e:
            print(e)
            return 2
        draft.setdefault("_meta", {})["channel"] = ch
        draft["_meta"]["channel_label"] = config.channel_label(ch)

    meta = draft.get("_meta", {})
    print(f"Publishing: {draft.get('title')!r}")
    print(f"  channel: {meta.get('channel_label') or meta.get('channel', 'default')}")
    pa = str(draft.get("publish_at", "")).strip().lower()
    print(f"  mode: {'PUBLISH NOW' if pa in ('', 'now') else 'schedule @ ' + str(draft.get('publish_at'))}")

    from . import youtube as yt
    try:
        video_id = yt.upload(draft, timezone=settings.get("timezone", "Asia/Kolkata"))
    except Exception as e:
        print(f"\nUpload failed: {e}")
        return 1

    draft.setdefault("_meta", {})["video_id"] = video_id
    draft["_meta"]["published_at"] = datetime.now().isoformat()
    with draft_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(draft, fh, sort_keys=False, allow_unicode=True, width=100)
    print("\nDone.")
    return 0


def cmd_review(args) -> int:
    """Launch the editable review UI for a draft (edit in browser -> save -> publish)."""
    settings = config.settings()
    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(f"Draft not found: {draft_path}")
        return 2
    from . import reviewserver
    reviewserver.serve(draft_path, settings, open_browser=not args.no_open)
    return 0


def cmd_serve(args) -> int:
    """Launch the web app (React frontend + API)."""
    from . import webapp
    webapp.serve(port=args.port, open_browser=not args.no_open)
    return 0


def cmd_channels(args) -> int:
    """List configured channels and whether each is authorized yet."""
    from . import youtube as yt

    ch = config.channels()
    if not ch:
        print("No channels configured. Add a `channels:` block to config/settings.yaml.")
        return 0
    default = config.default_channel()
    print("Configured channels:\n")
    for key, cfg in ch.items():
        token = yt._token_file(key)
        star = " (default)" if key == default else ""
        auth = "authorized" if token.exists() else f"NOT authorized - run: youtube_manager auth --channel {key}"
        profile = config._profile_path(key).name
        print(f"  - {key}{star}: {cfg.get('label','')}  {cfg.get('handle','')}")
        print(f"      profile: {profile} | {auth}")
    return 0


def cmd_auth(args) -> int:
    """Authorize a channel now (opens browser) and confirm which channel the token controls."""
    from . import youtube as yt

    try:
        channel_key = config.resolve_channel(args.channel)
    except ValueError as e:
        print(e)
        return 2
    print(f"Authorizing channel '{channel_key}' ({config.channel_label(channel_key)})...")
    try:
        service = yt.get_service(channel_key)
        info = yt.channel_info(service)
    except Exception as e:
        print(f"Auth failed: {e}")
        return 1
    print(f"\nAuthorized. This token controls: {info['title']}  (id {info['id']})")
    print(f"Saved to {yt._token_file(channel_key).name}")
    print("If that's the WRONG channel, delete that token file and re-run, picking the "
          "correct Brand Account in the browser.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="youtube_manager", description="YouTube upload & SEO agent")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("draft", help="generate an upload-ready draft")
    d.add_argument("source", help="Google Drive link OR local file path (either can be Short or long-form)")
    g = d.add_mutually_exclusive_group()
    g.add_argument("--long", action="store_true", help="force long-form (default: auto by duration)")
    g.add_argument("--short", action="store_true", help="force Short (default: auto by duration)")
    d.add_argument("--channel", help="which channel this is for (key/label/handle)")
    d.add_argument("--profile", help="override profile file for this draft (e.g. for a new niche / one-off)")
    d.add_argument("--thumbnail", help="long-form: local path or link to your thumbnail")
    d.add_argument("--slug", help="name for the draft files")
    d.add_argument("--no-review", action="store_true",
                   help="don't auto-open the review UI; just write the draft")
    d.set_defaults(func=cmd_draft)

    pub = sub.add_parser("publish", help="upload/schedule a reviewed draft")
    pub.add_argument("draft", help="path to drafts/<slug>.yaml")
    pub.add_argument("--channel", help="override the channel recorded in the draft")
    pub.set_defaults(func=cmd_publish)

    rv = sub.add_parser("review", help="edit a draft in the browser, then publish")
    rv.add_argument("draft", help="path to drafts/<slug>.yaml")
    rv.add_argument("--no-open", action="store_true", help="don't auto-open the browser")
    rv.set_defaults(func=cmd_review)

    sv = sub.add_parser("serve", help="launch the web app (React UI + API)")
    sv.add_argument("--port", type=int, default=8765, help="port (default 8765)")
    sv.add_argument("--no-open", action="store_true", help="don't auto-open the browser")
    sv.set_defaults(func=cmd_serve)

    ch = sub.add_parser("channels", help="list configured channels + auth status")
    ch.set_defaults(func=cmd_channels)

    au = sub.add_parser("auth", help="log in / verify a channel")
    au.add_argument("--channel", help="channel key/label/handle (default: the default channel)")
    au.set_defaults(func=cmd_auth)
    return p


def main(argv=None) -> int:
    # Windows consoles default to cp1252; ranking titles / raw titles can contain
    # emoji or non-Latin text. Force UTF-8 so printing them never crashes.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
