"""Background job worker (Oracle VM) — runs generate/publish jobs off the web process.

    REDIS_URL=redis://localhost:6379 python worker.py

Run this as its own long-lived process (systemd service) alongside gunicorn. It
pulls jobs enqueued by RQJobQueue (see jobqueue.py).
"""
import os

from youtube_manager.logging_setup import configure_logging, get_logger


def main() -> None:
    configure_logging()
    url = os.environ.get("REDIS_URL")
    if not url:
        raise SystemExit("REDIS_URL is not set — the worker needs Redis.")
    from redis import Redis
    from rq import Queue, Worker
    conn = Redis.from_url(url)
    get_logger("youtube_manager.worker").info("Worker starting, listening on 'default'")
    Worker([Queue("default", connection=conn)], connection=conn).work()


if __name__ == "__main__":
    main()
