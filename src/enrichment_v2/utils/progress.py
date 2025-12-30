"""
Progress tracker with checkpoint/resume capability

Tracks enrichment progress and enables resuming from last checkpoint.

Features:
- JSON-based state persistence
- Thread-safe operations
- Automatic checkpointing
- Statistics tracking
- Status queries
"""

import json
import threading
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PracticeStatus(Enum):
    """Status of practice enrichment"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PracticeProgress:
    """Progress information for a single practice"""
    practice_id: str
    status: PracticeStatus
    attempt_count: int = 0
    last_attempt: Optional[str] = None  # ISO datetime
    error_message: Optional[str] = None
    scraper_method: Optional[str] = None
    pages_crawled: int = 0
    ai_cost: float = 0.0
    enriched_at: Optional[str] = None  # ISO datetime

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization"""
        d = asdict(self)
        d['status'] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> 'PracticeProgress':
        """Create from dict"""
        d = d.copy()
        d['status'] = PracticeStatus(d['status'])
        return cls(**d)


class ProgressTracker:
    """
    Thread-safe progress tracker for enrichment system.

    Automatically saves to disk at intervals.
    Supports resuming from last checkpoint.
    """

    def __init__(
        self,
        state_file: Path,
        checkpoint_interval: int = 10,
        auto_save: bool = True
    ):
        """
        Initialize progress tracker.

        Args:
            state_file: Path to JSON state file
            checkpoint_interval: Save every N updates
            auto_save: Automatically save to disk
        """
        self.state_file = Path(state_file)
        self.checkpoint_interval = checkpoint_interval
        self.auto_save = auto_save

        self._practices: Dict[str, PracticeProgress] = {}
        self._update_count = 0
        self._lock = threading.RLock()

        # Statistics
        self._stats = {
            'total_practices': 0,
            'pending': 0,
            'in_progress': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total_cost': 0.0,
            'start_time': None,
            'last_update': None,
        }

        # Load existing state if available
        self.load()

    def initialize_practices(self, practice_ids: List[str], reset: bool = False):
        """
        Initialize tracker with practice IDs.

        Args:
            practice_ids: List of practice IDs to track
            reset: If True, reset existing progress
        """
        with self._lock:
            if reset:
                self._practices.clear()

            for practice_id in practice_ids:
                if practice_id not in self._practices or reset:
                    self._practices[practice_id] = PracticeProgress(
                        practice_id=practice_id,
                        status=PracticeStatus.PENDING
                    )

            self._stats['total_practices'] = len(self._practices)
            self._stats['start_time'] = datetime.now().isoformat()
            self._update_statistics()

            if self.auto_save:
                self.save()

    def update_status(
        self,
        practice_id: str,
        status: PracticeStatus,
        **kwargs
    ):
        """
        Update practice status.

        Args:
            practice_id: Practice ID
            status: New status
            **kwargs: Additional fields to update (error_message, scraper_method, etc.)
        """
        with self._lock:
            if practice_id not in self._practices:
                logger.warning(f"Practice {practice_id} not in tracker, adding it")
                self._practices[practice_id] = PracticeProgress(
                    practice_id=practice_id,
                    status=status
                )
            else:
                progress = self._practices[practice_id]
                progress.status = status
                progress.last_attempt = datetime.now().isoformat()

                # Update additional fields
                for key, value in kwargs.items():
                    if hasattr(progress, key):
                        setattr(progress, key, value)

                # Increment attempt count if in progress
                if status == PracticeStatus.IN_PROGRESS:
                    progress.attempt_count += 1

                # Set enriched_at on success
                if status == PracticeStatus.SUCCESS and not progress.enriched_at:
                    progress.enriched_at = datetime.now().isoformat()

            self._update_count += 1
            self._stats['last_update'] = datetime.now().isoformat()
            self._update_statistics()

            # Auto-save at intervals
            if self.auto_save and self._update_count % self.checkpoint_interval == 0:
                self.save()

    def get_status(self, practice_id: str) -> Optional[PracticeStatus]:
        """Get status of a practice"""
        with self._lock:
            progress = self._practices.get(practice_id)
            return progress.status if progress else None

    def get_progress(self, practice_id: str) -> Optional[PracticeProgress]:
        """Get full progress info for a practice"""
        with self._lock:
            return self._practices.get(practice_id)

    def get_pending(self) -> List[str]:
        """Get list of pending practice IDs"""
        with self._lock:
            return [
                pid for pid, progress in self._practices.items()
                if progress.status == PracticeStatus.PENDING
            ]

    def get_failed(self) -> List[str]:
        """Get list of failed practice IDs"""
        with self._lock:
            return [
                pid for pid, progress in self._practices.items()
                if progress.status == PracticeStatus.FAILED
            ]

    def get_successful(self) -> List[str]:
        """Get list of successful practice IDs"""
        with self._lock:
            return [
                pid for pid, progress in self._practices.items()
                if progress.status == PracticeStatus.SUCCESS
            ]

    def get_skipped(self) -> List[str]:
        """Get list of skipped practice IDs"""
        with self._lock:
            return [
                pid for pid, progress in self._practices.items()
                if progress.status == PracticeStatus.SKIPPED
            ]

    def _update_statistics(self):
        """Update internal statistics (assumes lock is held)"""
        self._stats['pending'] = sum(
            1 for p in self._practices.values()
            if p.status == PracticeStatus.PENDING
        )
        self._stats['in_progress'] = sum(
            1 for p in self._practices.values()
            if p.status == PracticeStatus.IN_PROGRESS
        )
        self._stats['success'] = sum(
            1 for p in self._practices.values()
            if p.status == PracticeStatus.SUCCESS
        )
        self._stats['failed'] = sum(
            1 for p in self._practices.values()
            if p.status == PracticeStatus.FAILED
        )
        self._stats['skipped'] = sum(
            1 for p in self._practices.values()
            if p.status == PracticeStatus.SKIPPED
        )
        self._stats['total_cost'] = sum(
            p.ai_cost for p in self._practices.values()
        )

    def get_stats(self) -> dict:
        """Get current statistics"""
        with self._lock:
            return self._stats.copy()

    def print_stats(self):
        """Print formatted statistics"""
        stats = self.get_stats()

        total = stats['total_practices']
        if total == 0:
            print("No practices tracked yet")
            return

        print("\n" + "="*60)
        print("ENRICHMENT PROGRESS")
        print("="*60)
        print(f"Total Practices:  {total:,}")
        print(f"Success:          {stats['success']:,} ({stats['success']/total*100:.1f}%)")
        print(f"Failed:           {stats['failed']:,} ({stats['failed']/total*100:.1f}%)")
        print(f"Pending:          {stats['pending']:,} ({stats['pending']/total*100:.1f}%)")
        print(f"In Progress:      {stats['in_progress']:,}")
        print(f"Skipped:          {stats['skipped']:,}")
        print(f"Total AI Cost:    ${stats['total_cost']:.2f}")

        if stats['start_time']:
            print(f"Started:          {stats['start_time']}")
        if stats['last_update']:
            print(f"Last Update:      {stats['last_update']}")

        print("="*60 + "\n")

    def save(self):
        """Save state to disk"""
        with self._lock:
            state = {
                'practices': {
                    pid: progress.to_dict()
                    for pid, progress in self._practices.items()
                },
                'statistics': self._stats.copy(),
                'last_saved': datetime.now().isoformat(),
            }

            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file first, then rename (atomic)
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self.state_file)

            # Log every 10 saves to avoid spam (saves happen after every practice now)
            if self._stats['success'] % 10 == 0:
                logger.info(f"Saved progress: {self._stats['success']}/{self._stats['total_practices']} succeeded")
            else:
                logger.debug(f"Auto-saved: {self._stats['success']} practices complete")

    def load(self):
        """Load state from disk"""
        if not self.state_file.exists():
            logger.info("No existing progress file found, starting fresh")
            return

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)

            with self._lock:
                self._practices = {
                    pid: PracticeProgress.from_dict(data)
                    for pid, data in state.get('practices', {}).items()
                }
                self._stats.update(state.get('statistics', {}))
                self._update_statistics()

            logger.info(f"Loaded progress: {len(self._practices)} practices")
            self.print_stats()

        except Exception as e:
            logger.error(f"Error loading progress file: {e}")
            logger.warning("Starting with fresh state")

    def reset(self):
        """Reset all progress"""
        with self._lock:
            for progress in self._practices.values():
                progress.status = PracticeStatus.PENDING
                progress.attempt_count = 0
                progress.last_attempt = None
                progress.error_message = None
                progress.scraper_method = None
                progress.pages_crawled = 0
                progress.ai_cost = 0.0
                progress.enriched_at = None

            self._update_count = 0
            self._stats['start_time'] = datetime.now().isoformat()
            self._update_statistics()

            if self.auto_save:
                self.save()

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"<ProgressTracker total={stats['total_practices']} "
            f"success={stats['success']} pending={stats['pending']}>"
        )
