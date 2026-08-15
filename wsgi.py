"""Production WSGI entrypoint for the hosted backend (Oracle VM).

Run with gunicorn (do NOT use the Flask dev server in prod):

    gunicorn -w 2 -k gthread --threads 8 --timeout 120 -b 127.0.0.1:8765 wsgi:app

(2 worker processes × 8 threads handles concurrent requests; the heavy generate/
publish work runs on the separate rq worker — see worker.py.)
"""
from youtube_manager.logging_setup import configure_logging
from youtube_manager.webapp import create_app

configure_logging()
app = create_app()
