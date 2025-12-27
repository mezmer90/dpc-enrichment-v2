"""
Celery Tasks Package

Background task processing for DPC enrichment.
"""

from celery import Celery
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Celery app
# Handle empty REDIS_URL by falling back to default
redis_url = os.getenv('REDIS_URL') or 'redis://localhost:6379/0'
celery_app = Celery(
    'dpc_enrichment',
    broker=redis_url,
    backend=redis_url
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    result_expires=3600,  # Results expire after 1 hour
    task_acks_late=True,  # Acknowledge tasks after completion
    worker_prefetch_multiplier=1,  # Only take one task at a time
)

# Import tasks to register them with Celery
from .enrichment_task import enrich_practices_task

__all__ = ['celery_app', 'enrich_practices_task']
