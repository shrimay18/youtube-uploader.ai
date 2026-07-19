"""Editable local review UI.

`youtube_manager review <draft.yaml>` launches a small local web page where you edit the
title, description, tags, thumbnail, and publish settings, click **Save** to write
the changes back to draft.yaml, and click **Publish** to upload with those exact
edits. This is the "edit in the browser and it uploads what you edited" flow.
"""
from __future__ import annotations

import socket
import threading
import webbrowser
from pathlib import Path

import yaml

from .generate import CATEGORY_IDS


def _load(draft_path: Path) -> dict:
    with draft_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _save(draft_path: Path, draft: dict) -> None:
    with draft_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(draft, fh, sort_keys=False, allow_unicode=True, width=100)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _apply_form(draft: dict, form) -> dict:
    """Merge posted form fields back into the draft dict."""
    draft["title"] = form.get("title", draft.get("title", "")).strip()
    draft["description"] = form.get("description", draft.get("description", ""))
    draft["pinned_comment"] = form.get("pinned_comment", draft.get("pinned_comment", ""))

    # Tags: comma or newline separated -> clean list.
    raw_tags = form.get("tags", "")
    tags = [t.strip() for t in raw_tags.replace("\n", ",").split(",") if t.strip()]
    draft["tags"] = tags

    raw_hash = form.get("hashtags", "")
    hashes = [h.strip() for h in raw_hash.replace("\n", ",").split(",") if h.strip()]
    draft["hashtags"] = [h if h.startswith("#") else f"#{h}" for h in hashes]

    cat_id = form.get("category_id", draft.get("category_id", "22"))
    draft["category_id"] = str(cat_id)
    id_to_name = {v: k for k, v in CATEGORY_IDS.items()}
    draft["category"] = id_to_name.get(str(cat_id), draft.get("category", ""))

    # Compliance / language.
    draft["made_for_kids"] = form.get("made_for_kids") == "on"
    draft["audio_language"] = form.get("audio_language", draft.get("audio_language", "")).strip()

    # Publish mode.
    mode = form.get("publish_mode", "private")
    if mode == "now":
        draft["privacy"] = "public"
        draft["publish_at"] = "now"
    elif mode == "schedule":
        draft["privacy"] = "private"
        draft["publish_at"] = form.get("publish_at", "").strip() or "none"
    else:  # private
        draft["privacy"] = "private"
        draft["publish_at"] = "none"
    return draft


def create_app(draft_path: Path, settings: dict):
    from flask import Flask, request, send_file, Response

    app = Flask(__name__)
    timezone = settings.get("timezone", "Asia/Kolkata")
    state = {"draft": _load(draft_path), "flash": ""}

    @app.route("/thumb")
    def thumb():
        p = str(state["draft"].get("thumbnail", "")).strip()
        if p and Path(p).exists():
            return send_file(p)
        return Response(status=404)

    @app.route("/", methods=["GET"])
    def index():
        html = _render(state["draft"], timezone, state["flash"])
        state["flash"] = ""
        return html

    @app.route("/save", methods=["POST"])
    def save():
        state["draft"] = _apply_form(state["draft"], request.form)
        _save(draft_path, state["draft"])
        state["flash"] = "Saved to draft.yaml."
        return _redirect()

    @app.route("/publish", methods=["POST"])
    def publish():
        state["draft"] = _apply_form(state["draft"], request.form)
        _save(draft_path, state["draft"])
        from . import youtube as yt
        logs: list[str] = []
        try:
            video_id = yt.upload(state["draft"], timezone=timezone, progress=logs.append)
            state["draft"].setdefault("_meta", {})["video_id"] = video_id
            _save(draft_path, state["draft"])
            state["flash"] = "PUBLISHED: https://youtu.be/" + video_id + "  |  " + " · ".join(logs)
        except Exception as e:  # OAuth not set up yet, etc.
            state["flash"] = f"Publish failed: {e}"
        return _redirect()

    @app.route("/thumbnail", methods=["POST"])
    def thumbnail_upload():
        f = request.files.get("thumbfile")
        if f and f.filename:
            dest = draft_path.parent.parent / "downloads" / f"{draft_path.stem}_custom{Path(f.filename).suffix}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            f.save(str(dest))
            state["draft"]["thumbnail"] = str(dest)
            _save(draft_path, state["draft"])
            state["flash"] = "Thumbnail replaced."
        return _redirect()

    def _redirect():
        return Response(status=303, headers={"Location": "/"})

    return app


def serve(draft_path: Path, settings: dict, open_browser: bool = True) -> None:
    app = create_app(draft_path, settings)
    port = _free_port()
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"\nReview UI running at {url}")
    print("Edit -> Save -> Publish in the browser. Press Ctrl+C here to stop.\n")
    # threaded=False keeps uploads (long, blocking) simple and ordered.
    app.run(host="127.0.0.1", port=port, debug=False)


# ---------------------------------------------------------------- template

def _render(d: dict, timezone: str, flash: str) -> str:
    from jinja2 import Template

    meta = d.get("_meta", {})
    tf = d.get("_title_flow", {})
    tags_str = ", ".join(d.get("tags", []))
    tags_len = _tags_char_len(d.get("tags", []))
    hashes_str = ", ".join(d.get("hashtags", []))
    pa = str(d.get("publish_at", "")).strip().lower()
    mode = "now" if pa == "now" else ("schedule" if pa not in ("", "none", "keep", "private") else "private")
    cats = sorted(CATEGORY_IDS.items(), key=lambda kv: kv[0])
    # Prefer scored options; fall back to plain variants (older drafts).
    options = d.get("title_options") or [{"title": t, "score": None} for t in d.get("title_variants", [])]
    return Template(_HTML).render(
        d=d, meta=meta, tf=tf, tags_str=tags_str, tags_len=tags_len,
        hashes_str=hashes_str, mode=mode, cats=cats, cur_cat=str(d.get("category_id", "22")),
        options=options, flash=flash, timezone=timezone,
    )


def _tags_char_len(tags: list[str]) -> int:
    total = 0
    for i, t in enumerate(tags):
        total += len(t) + (2 if " " in t else 0) + (1 if i else 0)
    return total


_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>TubeMate review — {{ d.title }}</title>
<style>
 :root{color-scheme:light dark}
 *{box-sizing:border-box}
 body{font-family:system-ui,Segoe UI,Roboto,sans-serif;max-width:860px;margin:1.5rem auto;padding:0 1rem;line-height:1.5}
 h1{font-size:1.25rem;margin:.2rem 0}
 .muted{opacity:.6;font-size:.85rem}
 .card{border:1px solid #8884;border-radius:12px;padding:1rem 1.2rem;margin:1rem 0}
 label{font-weight:600;display:block;margin:.2rem 0 .3rem}
 input[type=text],textarea,select{width:100%;padding:.55rem;border:1px solid #8886;border-radius:8px;font:inherit;background:#8881}
 textarea{resize:vertical}
 .row{display:flex;gap:1rem;flex-wrap:wrap}
 .row>div{flex:1;min-width:220px}
 img{max-width:220px;border-radius:10px}
 .btn{padding:.6rem 1.1rem;border:0;border-radius:8px;font:inherit;font-weight:600;cursor:pointer}
 .save{background:#4a90d9;color:#fff}
 .pub{background:#1a9e5f;color:#fff}
 .bar{position:sticky;bottom:0;background:var(--b,#fff);padding:.8rem 0;display:flex;gap:.6rem;align-items:center}
 @media (prefers-color-scheme:dark){.bar{--b:#111}}
 .flash{background:#4a90d922;border:1px solid #4a90d9;border-radius:8px;padding:.6rem .8rem;margin:.6rem 0;word-break:break-all}
 .count{font-weight:400}
 .count.over{color:#e2544a;font-weight:700}
 details summary{cursor:pointer}
 .pill{display:inline-block;background:#8882;border-radius:999px;padding:.1rem .5rem;margin:.1rem;font-size:.8rem}
 .opts{margin-top:.6rem;display:flex;flex-direction:column;gap:.35rem}
 .opt{display:flex;align-items:center;gap:.6rem;padding:.4rem .55rem;border:1px solid #8883;border-radius:8px;font-weight:400;cursor:pointer}
 .opt:hover{background:#8881}
 .opt input{margin:0}
 .otext{flex:1}
 .score{min-width:2.4rem;text-align:center;font-weight:700;font-size:.8rem;padding:.15rem .4rem;border-radius:6px;color:#fff}
 .score.good{background:#1a9e5f}
 .score.ok{background:#c9971a}
 .score.low{background:#e2544a}
</style></head><body>
<p class="muted">TubeMate review · <b>▶ {{ meta.channel_label or meta.channel }}</b> · {{ meta.kind }} · engine: {{ meta.engine }}</p>
{% if flash %}<div class="flash">{{ flash }}</div>{% endif %}

<form method="post" id="f">
<div class="card">
  <label>Title <span class="muted">(max 100 chars · pick a scored option or edit your own)</span></label>
  <input type="text" name="title" id="title" maxlength="100" value="{{ d.title }}">
  {% if options %}
  <div class="opts">
    {% for o in options %}
    <label class="opt">
      <input type="radio" name="titlepick" value="{{ o.title }}" {{ 'checked' if o.title==d.title }}
             onclick="document.getElementById('title').value=this.value">
      {% if o.score is not none %}<span class="score {{ 'good' if o.score>=75 else ('ok' if o.score>=60 else 'low') }}">{{ o.score }}</span>{% endif %}
      <span class="otext">{{ o.title }}</span>
    </label>
    {% endfor %}
  </div>
  {% endif %}
  {% if tf %}<details style="margin-top:.6rem"><summary class="muted">how these titles were made (best SEO score {{ tf.score }}/100)</summary>
   <p class="muted">Raw understanding: <i>{{ tf.raw_title }}</i></p>
   {% if tf.reference_title %}<p class="muted">Reference (from ranking patterns): <i>{{ tf.reference_title }}</i></p>{% endif %}
   {% if tf.ranking_titles %}<p class="muted">Top ranking titles studied:</p>{% for r in tf.ranking_titles %}<span class="pill">{{ r }}</span>{% endfor %}{% endif %}
  </details>{% endif %}
</div>

<div class="card">
  <label>Description</label>
  <textarea name="description" rows="12">{{ d.description }}</textarea>
</div>

<div class="card">
  <label>Tags <span class="muted count" id="tagcount">({{ tags_len }}/500 chars)</span></label>
  <textarea name="tags" id="tags" rows="3" oninput="tagcount()">{{ tags_str }}</textarea>
  <p class="muted">Comma-separated. YouTube allows 500 characters total; over-budget tags are dropped at upload.</p>
  <label>Hashtags</label>
  <input type="text" name="hashtags" value="{{ hashes_str }}">
</div>

<div class="row">
  <div class="card">
    <label>Thumbnail</label>
    <img src="/thumb?t={{ range(100000)|random }}" alt="(none)"><br><br>
    <input type="file" name="thumbfile" form="thumbform" accept="image/*">
    <button class="btn save" form="thumbform" formaction="/thumbnail" type="submit">Replace thumbnail</button>
  </div>
  <div class="card">
    <label>Category</label>
    <select name="category_id">
      {% for name,cid in cats %}<option value="{{ cid }}" {{ 'selected' if cid==cur_cat }}>{{ name }}</option>{% endfor %}
    </select>
    <label style="margin-top:.8rem">Pinned comment</label>
    <textarea name="pinned_comment" rows="3">{{ d.pinned_comment }}</textarea>
  </div>
</div>

<div class="card">
  <label>Compliance &amp; language</label>
  <label class="muted"><input type="checkbox" name="made_for_kids" {{ 'checked' if d.made_for_kids }}> Made for kids (COPPA) — leave OFF unless the video is child-directed</label>
  <label class="muted" style="margin-top:.4rem">Audio language:
    <input type="text" name="audio_language" style="width:6rem;display:inline-block" value="{{ d.audio_language }}" placeholder="hi / en"> <span class="muted">(auto-detected; edit if wrong)</span></label>
  <p class="muted" style="margin-top:.4rem">AI/altered-content disclosure isn't set here — this is real footage, and YouTube only accepts that flag in Studio (leave it "No").</p>
</div>

<div class="card">
  <label>Publish</label>
  <label class="muted"><input type="radio" name="publish_mode" value="private" {{ 'checked' if mode=='private' }}> Upload &amp; stay <b>private</b> (you publish manually later)</label>
  <label class="muted"><input type="radio" name="publish_mode" value="now" {{ 'checked' if mode=='now' }}> Publish <b>now</b> (public immediately)</label>
  <label class="muted"><input type="radio" name="publish_mode" value="schedule" {{ 'checked' if mode=='schedule' }}> <b>Schedule</b> (IST):
    <input type="text" name="publish_at" style="width:auto;display:inline-block" value="{{ d.publish_at }}" placeholder="2026-07-12T18:00:00+05:30"></label>
</div>

<div class="bar">
  <button class="btn save" formaction="/save" type="submit">💾 Save</button>
  <button class="btn pub" formaction="/publish" type="submit" onclick="return confirm('Upload this to YouTube now with the current edits?')">⬆ Publish / Schedule</button>
  <span class="muted">Save writes draft.yaml · Publish uploads with your edits</span>
</div>
</form>

<form id="thumbform" method="post" enctype="multipart/form-data"></form>

<script>
function tagcount(){
  var v=document.getElementById('tags').value;
  var parts=v.split(/[,\n]/).map(s=>s.trim()).filter(Boolean);
  var total=0; parts.forEach((t,i)=>{ total+=t.length+(t.includes(' ')?2:0)+(i?1:0); });
  var el=document.getElementById('tagcount');
  el.textContent='('+total+'/500 chars)';
  el.className='muted count'+(total>500?' over':'');
}
tagcount();
</script>
</body></html>"""
