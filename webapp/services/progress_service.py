"""
Progress Service

Real-time progress updates via Redis pub/sub for Server-Sent Events (SSE).
"""

import json
import redis
import os
from typing import Dict, Any, Generator
from datetime import datetime
from enum import Enum

# Redis connection
redis_client = redis.from_url(
    os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    decode_responses=True
)

PROGRESS_CHANNEL = 'dpc:enrichment:progress'


class ProgressEvent(str, Enum):
    """Progress event types"""
    STARTED = 'started'
    PRACTICE_STARTED = 'practice_started'
    PRACTICE_COMPLETED = 'practice_completed'
    PRACTICE_FAILED = 'practice_failed'
    PRACTICE_SKIPPED = 'practice_skipped'
    CHECKPOINT = 'checkpoint'
    PAUSED = 'paused'
    RESUMED = 'resumed'
    COMPLETED = 'completed'
    ERROR = 'error'
    STATS_UPDATE = 'stats_update'


def publish_progress(
    event: ProgressEvent,
    run_id: int,
    data: Dict[str, Any]
) -> None:
    """
    Publish progress update to Redis channel.

    Args:
        event: Type of progress event
        run_id: Enrichment run ID
        data: Event data (practice info, stats, etc.)
    """
    message = {
        'event': event.value,
        'run_id': run_id,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }

    try:
        redis_client.publish(PROGRESS_CHANNEL, json.dumps(message))
    except Exception as e:
        # Don't fail enrichment if Redis publish fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to publish progress: {e}")


def subscribe_to_progress() -> Generator[Dict[str, Any], None, None]:
    """
    Subscribe to progress updates from Redis.

    Yields:
        Progress update dictionaries for SSE streaming
    """
    pubsub = redis_client.pubsub()
    pubsub.subscribe(PROGRESS_CHANNEL)

    try:
        # Send initial connection message
        yield {
            'event': 'connected',
            'timestamp': datetime.utcnow().isoformat(),
            'message': 'Connected to progress stream'
        }

        # Listen for messages
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    yield data
                except json.JSONDecodeError:
                    continue

    except GeneratorExit:
        pubsub.unsubscribe(PROGRESS_CHANNEL)
        pubsub.close()


def get_current_stats(run_id: int) -> Dict[str, Any]:
    """
    Get current enrichment statistics from Redis cache.

    Args:
        run_id: Enrichment run ID

    Returns:
        Current statistics dictionary
    """
    cache_key = f'dpc:enrichment:stats:{run_id}'

    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    return {
        'total': 0,
        'completed': 0,
        'failed': 0,
        'skipped': 0,
        'in_progress': 0
    }


def update_stats_cache(run_id: int, stats: Dict[str, Any]) -> None:
    """
    Update enrichment statistics in Redis cache.

    Args:
        run_id: Enrichment run ID
        stats: Statistics dictionary
    """
    cache_key = f'dpc:enrichment:stats:{run_id}'

    try:
        redis_client.setex(
            cache_key,
            3600,  # Expire after 1 hour
            json.dumps(stats)
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to update stats cache: {e}")


def set_run_control(run_id: int, action: str) -> None:
    """
    Set control action for enrichment run (pause/resume/stop).

    Args:
        run_id: Enrichment run ID
        action: Control action (pause/resume/stop)
    """
    control_key = f'dpc:enrichment:control:{run_id}'

    try:
        redis_client.setex(
            control_key,
            600,  # Expire after 10 minutes
            action
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to set run control: {e}")


def get_run_control(run_id: int) -> str:
    """
    Get control action for enrichment run.

    Args:
        run_id: Enrichment run ID

    Returns:
        Control action (pause/resume/stop) or empty string
    """
    control_key = f'dpc:enrichment:control:{run_id}'

    try:
        action = redis_client.get(control_key)
        return action or ''
    except Exception:
        return ''


def clear_run_control(run_id: int) -> None:
    """
    Clear control action for enrichment run.

    Args:
        run_id: Enrichment run ID
    """
    control_key = f'dpc:enrichment:control:{run_id}'

    try:
        redis_client.delete(control_key)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to clear run control: {e}")
