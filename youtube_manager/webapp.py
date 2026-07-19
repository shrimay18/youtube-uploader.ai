"""TubeMate web API — Flask backend for the React frontend.

Long-running work (generate, publish) runs in background threads tracked as "jobs";
the frontend polls GET /api/jobs/<id> for progress. Static build (frontend/dist) is
served at / when present.

Endpoints
  GET  /api/health
  GET  /api/channels
  POST /api/generate                 -> {job_id}          (multipart form)
  GET  /api/jobs/<id>                 -> {status, stage, log, slug, result, error}
  GET  /api/drafts                    -> [{slug, title, ...}]
  GET  /api/drafts/<slug>             -> draft dict
  PUT  /api/drafts/<slug>             -> save edits (json)
  POST /api/drafts/<slug>/publish     -> {job_id}
  POST /api/drafts/<slug>/thumbnail   -> upload replacement thumbnail
  GET  /api/drafts/<slug>/thumb       -> thumbnail image
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

import yaml

from . import config, pipeline, vault
from .providers.base import QuotaExceeded

# job_id -> dict(status, stage, log, slug, result, error)
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()

_EDITABLE_KEYS = {
    "title", "description", "tags", "hashtags", "category_id", "category",
    "pinned_comment", "thumbnail_text", "privacy", "publish_at", "made_for_kids",
    "audio_language", "language", "title_options", "title_variants",
}


def _new_job(kind: str, slug: str = "") -> str:
    jid = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[jid] = {
            "id": jid, "kind": kind, "status": "running", "stage": "starting",
            "log": [], "slug": slug, "result": None, "error": None,
        }
    return jid


def _log(jid: str):
    def cb(msg: str):
        msg = str(msg)
        with _LOCK:
            j = _JOBS.get(jid)
            if j:
                j["log"].append(msg)
                stripped = msg.strip()
                if stripped and not stripped.startswith(" "):
                    j["stage"] = stripped[:120]
    return cb


def _draft_path(slug: str) -> Path:
    return config.paths().drafts / f"{slug}.yaml"


def _load_draft(slug: str) -> dict | None:
    p = _draft_path(slug)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _save_draft(slug: str, draft: dict) -> None:
    with _draft_path(slug).open("w", encoding="utf-8") as fh:
        yaml.safe_dump(draft, fh, sort_keys=False, allow_unicode=True, width=100)


def create_app():
    from flask import Flask, request, jsonify, send_file, Response

    root = config.ROOT
    dist = root / "frontend" / "dist"
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024  # 4 GB uploads

    # ---- Auth (local, single-user; keys encrypted on this device) ----
    OPEN = {"/api/health", "/api/config", "/api/auth/status", "/api/auth/setup",
            "/api/auth/login", "/api/auth/env-detected", "/api/auth/supabase"}

    @app.before_request
    def _guard():
        p = request.path
        if p.startswith("/api/") and p not in OPEN and not vault.is_authed():
            return jsonify({"error": "auth required"}), 401

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/config")
    def public_config():
        """Public frontend config (Supabase url + anon key). Non-secret by design."""
        return jsonify(config.supabase_config())

    @app.get("/api/auth/status")
    def auth_status():
        sb = config.supabase_config()
        email = vault.account_email()
        return jsonify({
            "account_exists": vault.account_exists(),
            "authed": vault.is_authed(),
            "method": vault.account_method(),
            "email": email,
            "has_google": bool(sb.get("url") and sb.get("anon_key")),
            "is_admin": vault.is_authed() and config.is_admin(email),
        })

    @app.get("/api/admin/stats")
    def admin_stats():
        if not config.is_admin(vault.account_email()):
            return jsonify({"error": "Not authorized."}), 403
        from . import admin
        try:
            return jsonify(admin.stats())
        except Exception as e:
            return jsonify({"error": f"Could not load stats: {str(e)[:160]}"}), 502

    @app.post("/api/auth/supabase")
    def auth_supabase():
        """Verify a Supabase access token, then unlock/create the local vault."""
        from . import supabase_auth
        b = request.get_json(silent=True) or {}
        claims = supabase_auth.verify(b.get("access_token", ""))
        if not claims:
            return jsonify({"error": "Sign-in could not be verified. Please try again."}), 401
        _sub, email, _name = supabase_auth.identity(claims)
        vault.supabase_login(email, b.get("keys", {}) or {})
        return jsonify({"ok": True, "email": email})

    @app.post("/api/auth/setup")
    def auth_setup():
        if vault.account_exists():
            return jsonify({"error": "account already exists"}), 400
        b = request.get_json(force=True) or {}
        try:
            vault.setup(b.get("password", ""), b.get("keys", {}) or {})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"ok": True})

    @app.get("/api/auth/env-detected")
    def env_detected():
        import os
        return jsonify({k: bool(os.environ.get(k)) for k in vault.KEY_FIELDS})

    @app.post("/api/auth/login")
    def auth_login():
        b = request.get_json(force=True) or {}
        if vault.login(b.get("password", "")):
            return jsonify({"ok": True})
        return jsonify({"error": "Incorrect password."}), 401

    @app.post("/api/auth/logout")
    def auth_logout():
        vault.logout()
        return jsonify({"ok": True})

    @app.post("/api/auth/reset")
    def auth_reset():
        vault.reset()
        return jsonify({"ok": True})

    @app.get("/api/settings/keys")
    def get_keys():
        return jsonify(vault.masked_keys())

    @app.post("/api/settings/keys")
    def set_keys():
        try:
            vault.update_keys(request.get_json(force=True) or {})
        except PermissionError as e:
            return jsonify({"error": str(e)}), 401
        return jsonify({"ok": True})

    # ---- Connected YouTube accounts (publish targets) ----
    @app.get("/api/youtube/accounts")
    def yt_accounts():
        from . import accounts
        try:
            return jsonify(accounts.list_public())
        except PermissionError:
            return jsonify({"error": "auth required"}), 401

    @app.post("/api/youtube/connect")
    def yt_connect():
        """Blocking loopback OAuth so the user can add a YouTube account."""
        from . import accounts
        try:
            acct = accounts.connect()
            return jsonify(acct)
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 400
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Couldn't connect that account: {str(e)[:160]}"}), 400

    @app.delete("/api/youtube/accounts/<account_id>")
    def yt_remove(account_id):
        from . import accounts
        accounts.remove(account_id)
        return jsonify({"ok": True})

    @app.put("/api/youtube/accounts/<account_id>/profile")
    def yt_set_profile(account_id):
        from . import accounts
        body = request.get_json(force=True) or {}
        ok = accounts.set_profile(account_id, body)
        return (jsonify({"ok": True}) if ok else (jsonify({"error": "not found"}), 404))

    @app.get("/api/channels")
    def channels():
        out = []
        for key, cfg in config.channels().items():
            ok, missing = config.profile_is_filled(key)
            from . import youtube as yt
            out.append({
                "key": key, "label": cfg.get("label", key), "handle": cfg.get("handle", ""),
                "profile_ok": ok, "missing": missing,
                "authorized": yt._token_file(key).exists(),
            })
        return jsonify(out)

    @app.post("/api/resolve-drive")
    def resolve_drive():
        """Expand a Drive FOLDER link, or split multiple file links, into a video list."""
        import re
        data = request.get_json(force=True) or {}
        text = (data.get("input") or "").strip()
        links = re.findall(r"https?://\S+", text)
        if not links:
            return jsonify({"error": "No Drive links found."}), 400

        if len(links) == 1 and "/folders/" in links[0]:
            try:
                import gdown
                files = gdown.download_folder(url=links[0], skip_download=True, quiet=True) or []
            except Exception as e:
                return jsonify({"error": f"Couldn't read that folder ({e}). "
                                "Paste individual file links (one per line) instead."}), 400
            vext = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".flv", ".wmv",
                    ".mpeg", ".mpg", ".3gp", ".ts")
            parsed = []
            for f in files:
                fid = getattr(f, "id", None)
                name = getattr(f, "path", None) or getattr(f, "local_path", None) or getattr(f, "name", None)
                if fid is None and isinstance(f, (list, tuple)):
                    fid = f[0] if f else None
                    name = f[1] if len(f) > 1 else ""
                if fid:
                    parsed.append((fid, Path(str(name or "")).name))
            vids = [{"link": f"https://drive.google.com/file/d/{fid}/view", "name": n}
                    for fid, n in parsed if n.lower().endswith(vext)]
            if not vids and parsed:   # names without a video extension -> include all
                vids = [{"link": f"https://drive.google.com/file/d/{fid}/view", "name": n}
                        for fid, n in parsed]
            if not vids:
                return jsonify({"error": "Folder has no readable files. Paste individual "
                                "file links (one per line) instead."}), 400
            return jsonify({"videos": vids})

        # Multiple individual file links.
        return jsonify({"videos": [{"link": l, "name": ""} for l in links]})

    @app.post("/api/generate")
    def generate():
        settings = config.settings()
        form = request.form
        # Voice: a connected account's own profile (preferred) or a settings channel.
        voice_account = (form.get("voice_account") or "").strip()
        if voice_account:
            from . import accounts
            profile = accounts.profile_for(voice_account)
            if profile is None:
                return jsonify({"error": "That account is no longer connected."}), 400
            missing = config.check_profile(profile)
            if missing:
                return jsonify({"error": f"Set this account's voice first (missing: {', '.join(missing)})."}), 400
            channel_key = voice_account
            label = accounts.label_for(voice_account)
        else:
            channel = form.get("channel") or config.default_channel()
            try:
                channel_key = config.resolve_channel(channel)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            profile = config.channel_profile(channel_key)
            ok, missing = config.profile_is_filled(channel_key)
            if not ok:
                return jsonify({"error": f"Channel profile incomplete: {', '.join(missing)}"}), 400
            label = config.channel_label(channel_key)

        downloads = config.paths().downloads
        source_type = form.get("source_type", "drive")
        name = (form.get("name") or "").strip()

        # Resolve the video source (Drive link or uploaded file).
        if source_type == "upload":
            f = request.files.get("video")
            if not f or not f.filename:
                return jsonify({"error": "No video file uploaded"}), 400
            slug = pipeline.slugify(name or Path(f.filename).stem)
            dest = downloads / f"{slug}{Path(f.filename).suffix or '.mp4'}"
            f.save(str(dest))
            source = str(dest)
        else:
            source = (form.get("drive_link") or "").strip()
            if not source:
                return jsonify({"error": "No Drive link provided"}), 400
            slug = pipeline.slugify(name or "video")

        # Optional thumbnail (file upload or link).
        thumbnail = None
        tf = request.files.get("thumbnail")
        if tf and tf.filename:
            tdest = downloads / f"{slug}_provided{Path(tf.filename).suffix or '.jpg'}"
            tf.save(str(tdest))
            thumbnail = str(tdest)
        elif form.get("thumbnail_link"):
            thumbnail = form.get("thumbnail_link").strip()

        force_kind = form.get("force_kind") or None
        if force_kind not in ("short", "long"):
            force_kind = None

        fdt = form.get("fixed_desc_text", "")
        fdp = form.get("fixed_desc_position", "auto")
        fct = form.get("fixed_comment_text", "")
        fcm = form.get("fixed_comment_mode", "ai")

        jid = _new_job("generate", slug)

        def work():
            log = _log(jid)
            try:
                result = pipeline.build_draft(
                    settings, profile, source, channel_key, label, slug,
                    thumbnail=thumbnail, force_kind=force_kind,
                    fixed_desc_text=fdt, fixed_desc_position=fdp,
                    fixed_comment_text=fct, fixed_comment_mode=fcm, log=log,
                )
                with _LOCK:
                    _JOBS[jid].update(status="done", stage="done", slug=result.slug,
                                      result={"slug": result.slug, "title": result.title,
                                              "score": result.score, "kind": result.kind})
            except QuotaExceeded as e:
                with _LOCK:
                    _JOBS[jid].update(status="error", error=f"LLM quota hit: {e}")
            except Exception as e:  # surface any pipeline failure to the UI
                with _LOCK:
                    _JOBS[jid].update(status="error", error=str(e))

        threading.Thread(target=work, daemon=True).start()
        return jsonify({"job_id": jid, "slug": slug})

    @app.get("/api/jobs/<jid>")
    def job(jid):
        with _LOCK:
            j = _JOBS.get(jid)
            if not j:
                return jsonify({"error": "unknown job"}), 404
            return jsonify(dict(j))

    @app.get("/api/jobs")
    def jobs():
        """All jobs this server run knows about (for reconnecting after a reopen)."""
        with _LOCK:
            return jsonify([
                {"id": j["id"], "kind": j["kind"], "status": j["status"],
                 "stage": j["stage"], "slug": j["slug"], "result": j["result"],
                 "error": j["error"]}
                for j in _JOBS.values()
            ])

    @app.get("/api/drafts")
    def drafts():
        out = []
        for p in sorted(config.paths().drafts.glob("*.yaml"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                d = yaml.safe_load(p.read_text(encoding="utf-8"))
                m = d.get("_meta", {})
                out.append({"slug": m.get("slug", p.stem), "title": d.get("title", ""),
                            "channel": m.get("channel_label") or m.get("channel"),
                            "kind": m.get("kind"), "score": d.get("_title_flow", {}).get("score")})
            except Exception:
                continue
        return jsonify(out)

    @app.get("/api/drafts/<slug>")
    def get_draft(slug):
        d = _load_draft(slug)
        return (jsonify(d), 200) if d else (jsonify({"error": "not found"}), 404)

    @app.delete("/api/drafts/<slug>")
    def discard_draft(slug):
        """Discard a draft (opt out of upload) — delete the yaml + generated thumbnail."""
        p = _draft_path(slug)
        d = _load_draft(slug)
        meta = (d or {}).get("_meta", {})
        if d and (meta.get("video_id") or meta.get("publishes")):
            return jsonify({"error": "already published"}), 400
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
        dl = config.paths().downloads
        for pat in (f"{slug}_thumb.jpg", f"{slug}_frame.jpg", f"{slug}_custom.*", f"{slug}_provided.*"):
            for f in dl.glob(pat):
                try:
                    f.unlink(missing_ok=True)
                except OSError:
                    pass
        return jsonify({"ok": True})

    @app.put("/api/drafts/<slug>")
    def save_draft(slug):
        d = _load_draft(slug)
        if not d:
            return jsonify({"error": "not found"}), 404
        body = request.get_json(force=True) or {}
        for k, v in body.items():
            if k in _EDITABLE_KEYS:
                d[k] = v
        _save_draft(slug, d)
        return jsonify({"ok": True})

    @app.post("/api/drafts/<slug>/publish")
    def publish(slug):
        d = _load_draft(slug)
        if not d:
            return jsonify({"error": "not found"}), 404
        body = request.get_json(silent=True) or {}
        for k, v in body.items():           # accept last-minute edits with the publish call
            if k in _EDITABLE_KEYS:
                d[k] = v
        _save_draft(slug, d)
        settings = config.settings()

        # Optional publish target: a connected YouTube account.
        account_id = (body.get("account_id") or "").strip()
        token_json = None
        target_label = None
        if account_id:
            from . import accounts
            token_json = accounts.token_for(account_id)
            if not token_json:
                return jsonify({"error": "That YouTube account isn't connected."}), 400
            target_label = accounts.label_for(account_id)

        jid = _new_job("publish", slug)

        def work():
            log = _log(jid)
            from . import youtube as yt
            try:
                vid = yt.upload(d, timezone=settings.get("timezone", "Asia/Kolkata"),
                                progress=log, token_json=token_json)
                meta = d.setdefault("_meta", {})
                if account_id:                         # record each account's published video
                    meta.setdefault("publishes", {})[account_id] = vid
                else:
                    meta["video_id"] = vid
                _save_draft(slug, d)
                with _LOCK:
                    _JOBS[jid].update(status="done", stage="published",
                                      result={"video_id": vid, "url": f"https://youtu.be/{vid}",
                                              "account_id": account_id, "account": target_label})
            except Exception as e:
                with _LOCK:
                    _JOBS[jid].update(status="error", error=str(e))

        threading.Thread(target=work, daemon=True).start()
        return jsonify({"job_id": jid})

    @app.post("/api/drafts/<slug>/thumbnail")
    def set_thumb(slug):
        d = _load_draft(slug)
        if not d:
            return jsonify({"error": "not found"}), 404
        f = request.files.get("thumbnail")
        if not f or not f.filename:
            return jsonify({"error": "no file"}), 400
        dest = config.paths().downloads / f"{slug}_custom{Path(f.filename).suffix or '.jpg'}"
        f.save(str(dest))
        d["thumbnail"] = str(dest)
        _save_draft(slug, d)
        return jsonify({"ok": True})

    @app.get("/api/drafts/<slug>/thumb")
    def get_thumb(slug):
        d = _load_draft(slug)
        p = str((d or {}).get("thumbnail", "")).strip()
        if p and Path(p).exists():
            return send_file(p)
        return Response(status=404)

    # ---- Serve the built frontend (production) ----
    @app.get("/")
    def index():
        idx = dist / "index.html"
        if idx.exists():
            return send_file(idx)
        return Response(
            "Frontend not built. Run `npm --prefix frontend install && npm --prefix "
            "frontend run build`, or use the Vite dev server (npm --prefix frontend run dev).",
            mimetype="text/plain",
        )

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_file(dist / "assets" / filename)

    return app


def serve(port: int = 8765, open_browser: bool = True) -> None:
    import os
    import webbrowser

    app = create_app()
    url = f"http://127.0.0.1:{port}/"
    os.environ["TM_APP_URL"] = url  # so Google sign-in redirects back to the right port
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"\nyoutube_manager.ai web app: {url}")
    print("Press Ctrl+C to stop.\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
