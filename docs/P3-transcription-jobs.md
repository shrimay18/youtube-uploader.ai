# P3 — Transcription API + background job queue

**Built + tested** (`transcriber.py`, `jobqueue.py`; tests in `test_transcriber.py`,
`test_jobqueue.py`). Both are behind interfaces with local/in-memory defaults, so the
current app is unchanged. Integration = the deploy step.

## Transcription
Local Whisper is fine on a device but heavy on a server. `get_transcriber(settings)`
selects the implementation and all return the same `transcribe.Transcript`.

- **Selection:** env `TM_TRANSCRIBER` = `deepgram` | `openai` | `local` (default `local`).
- **Deepgram:** `DEEPGRAM_API_KEY` (nova-2). **OpenAI:** `OPENAI_API_KEY` (whisper-1).

**Integration in `pipeline.build_draft`:** extract audio once, then transcribe via the
interface:
```python
from . import transcribe as _t
from .transcriber import get_transcriber
audio = _t.extract_audio(video_path)                 # ffmpeg (already exists)
transcript = get_transcriber(settings).transcribe(str(audio))
```
(Replaces the direct `_t.transcribe(video_path)` call; the local path still works via
`LocalWhisperTranscriber`.) Cost note: transcription APIs bill per audio-minute — for a
*free* service, keep `local` on a cheap always-on VM, or make the API a paid tier.

## Background jobs
In-process threads die on an ephemeral host. `get_job_queue()` returns:
- **InMemoryJobQueue** (threads) when no `REDIS_URL` — local/dev, matches today.
- **RQJobQueue** (Redis + RQ) when `REDIS_URL` is set — a separate `rq worker` process.

Job fn signature: `fn(ctx)` where `ctx.log(msg)` / `ctx.stage(name)` report progress and
the return value is the result — the same shape `/api/jobs` already exposes.

**Integration in `webapp.py`:** replace `_new_job` + `threading.Thread` + the global
`_JOBS` dict with a module-level `queue = get_job_queue()`:
```python
def work(ctx):
    ctx.stage("generating")
    result = pipeline.build_draft(..., log=ctx.log)
    return {"slug": result.slug, "title": result.title, "score": result.score}
jid = queue.enqueue(work, kind="generate")
# GET /api/jobs/<id> -> queue.get(jid);  GET /api/jobs -> queue.list()
```
**Prod deps:** `pip install redis rq`; set `REDIS_URL`; run `rq worker` alongside the web
process. On Oracle/Render that's a second process (or a background worker service).

## Server-side video handling (also part of going hosted)
On a server there's no user disk: for a Drive link or upload, the backend downloads/receives
to a temp dir (or object storage — Supabase Storage / S3), extracts audio, transcribes,
uploads to YouTube, then deletes the source. Enforce a max file size and clean up in a
`finally`. This is wiring done during P4 integration, not new logic.

## Integration checklist (deploy)
1. `pip install redis rq` (prod); set `REDIS_URL`, `TM_TRANSCRIBER`, transcription key.
2. `pipeline`: extract audio once → `get_transcriber(settings).transcribe(audio)`.
3. `webapp`: swap the thread/`_JOBS` job system for `get_job_queue()`; run `rq worker`.
4. Temp-file/object-storage handling for source videos + cleanup.
