"""P3: background jobs behind a queue interface (InMemory impl)."""
from youtube_manager.jobqueue import InMemoryJobQueue


def test_job_success_captures_result_stage_and_log():
    q = InMemoryJobQueue()

    def work(ctx):
        ctx.stage("running")
        ctx.log("step 1")
        ctx.log("step 2")
        return {"ok": True, "n": 42}

    jid = q.enqueue(work, kind="generate")
    j = q.wait(jid)
    assert j["status"] == "done"
    assert j["result"] == {"ok": True, "n": 42}
    assert j["log"] == ["step 1", "step 2"]
    assert j["stage"] == "running"
    assert j["kind"] == "generate"


def test_job_error_is_captured():
    q = InMemoryJobQueue()

    def boom(ctx):
        raise ValueError("kaboom")

    j = q.wait(q.enqueue(boom))
    assert j["status"] == "error" and "kaboom" in j["error"]


def test_get_unknown_job_returns_none():
    assert InMemoryJobQueue().get("does-not-exist") is None


def test_sync_mode_runs_inline_and_lists():
    q = InMemoryJobQueue(sync=True)
    jid = q.enqueue(lambda ctx: {"a": 1}, kind="x")
    assert q.get(jid)["status"] == "done"            # finished immediately in sync mode
    q.enqueue(lambda ctx: {"b": 2}, kind="y")
    assert {j["kind"] for j in q.list()} == {"x", "y"}
