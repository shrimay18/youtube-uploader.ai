"""Background jobs behind one interface (P3).

Long tasks (generate, publish) can't run as in-process threads on an ephemeral host
(they die on restart/scale and don't fan out). This wraps them behind a JobQueue:
  - InMemoryJobQueue: threads + a dict (current behavior) — local dev / tests.
  - RQJobQueue: Redis + RQ — a real worker process in prod.

The enqueued function is `fn(ctx)`, where `ctx.log(msg)` / `ctx.stage(name)` report
progress and the return value becomes the job result. Same shape the webapp's
/api/jobs endpoints already expose, so swapping the queue is a small change.
"""
from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field


@dataclass
class JobRecord:
    id: str
    kind: str = ""
    status: str = "queued"          # queued | running | done | error
    stage: str = ""
    result: dict | None = None
    error: str | None = None
    log: list = field(default_factory=list)


class JobContext:
    """Handed to the job function so it can report progress + stages."""

    def __init__(self, rec: JobRecord):
        self._rec = rec

    def log(self, msg: str) -> None:
        self._rec.log.append(str(msg))

    def stage(self, name: str) -> None:
        self._rec.stage = name


class JobQueue(ABC):
    @abstractmethod
    def enqueue(self, fn, kind: str = "") -> str:
        """Enqueue fn(ctx)->result and return a job id."""

    @abstractmethod
    def get(self, job_id: str) -> dict | None: ...

    @abstractmethod
    def list(self) -> list[dict]: ...


class InMemoryJobQueue(JobQueue):
    def __init__(self, sync: bool = False):
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self.sync = sync            # sync=True runs inline (handy for tests)

    def enqueue(self, fn, kind: str = "") -> str:
        jid = uuid.uuid4().hex[:12]
        rec = JobRecord(id=jid, kind=kind)
        with self._lock:
            self._jobs[jid] = rec

        def run():
            rec.status = "running"
            try:
                rec.result = fn(JobContext(rec))
                rec.status = "done"
            except Exception as e:               # noqa: BLE001 — surface any failure as job error
                rec.error = str(e)
                rec.status = "error"

        if self.sync:
            run()
        else:
            threading.Thread(target=run, daemon=True).start()
        return jid

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            rec = self._jobs.get(job_id)
            return asdict(rec) if rec else None

    def list(self) -> list[dict]:
        with self._lock:
            return [asdict(r) for r in self._jobs.values()]

    def wait(self, job_id: str, timeout: float = 5.0) -> dict | None:
        """Block until the job finishes (test/dev convenience)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            j = self.get(job_id)
            if j and j["status"] in ("done", "error"):
                return j
            time.sleep(0.01)
        return self.get(job_id)


class RQJobQueue(JobQueue):
    """Prod queue: Redis + RQ. A separate worker (`rq worker`) runs the jobs.

    Progress log/stage live in the RQ job's `meta` (updated by the job fn via a
    context that writes to job.meta). Requires `redis` + `rq` and a running worker.
    """

    def __init__(self, redis_url: str, queue_name: str = "default"):
        from redis import Redis
        from rq import Queue
        self._q = Queue(queue_name, connection=Redis.from_url(redis_url))

    def enqueue(self, fn, kind: str = "") -> str:
        job = self._q.enqueue(fn, job_timeout=3600, meta={"kind": kind})
        return job.id

    def get(self, job_id: str) -> dict | None:
        from rq.job import Job
        try:
            job = Job.fetch(job_id, connection=self._q.connection)
        except Exception:
            return None
        meta = job.meta or {}
        return {
            "id": job.id, "kind": meta.get("kind", ""),
            "status": {"queued": "queued", "started": "running", "finished": "done",
                       "failed": "error"}.get(job.get_status(), job.get_status()),
            "stage": meta.get("stage", ""), "result": job.result,
            "error": (job.exc_info or "").splitlines()[-1] if job.is_failed else None,
            "log": meta.get("log", []),
        }

    def list(self) -> list[dict]:
        return [self.get(jid) for jid in self._q.job_ids]


def get_job_queue(settings: dict | None = None) -> JobQueue:
    """Pick the queue: env REDIS_URL => RQ, else in-process threads."""
    import os
    url = os.environ.get("REDIS_URL")
    return RQJobQueue(url) if url else InMemoryJobQueue()
