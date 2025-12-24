web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 3 --timeout 120
worker: celery -A webapp.tasks.celery_app worker --loglevel=info --concurrency=2
