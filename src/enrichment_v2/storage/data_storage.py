"""
Data storage for enriched practice data

Handles saving and loading of final enriched JSON data.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging
import shutil

logger = logging.getLogger(__name__)


class DataStorage:
    """
    Manages storage of enriched practice data in JSON format.

    Handles:
    - Saving enriched practices
    - Loading existing data
    - Creating backups
    - Atomic writes
    """

    @staticmethod
    def save_enriched(
        practices: List[Dict],
        output_file: Path,
        metadata: Optional[Dict] = None,
        create_backup: bool = True
    ):
        """
        Save enriched practices to JSON file.

        Args:
            practices: List of enriched practice dicts
            output_file: Output file path
            metadata: Optional metadata to include
            create_backup: Create backup if file exists

        Raises:
            Exception: If save fails
        """
        try:
            output_file = Path(output_file)

            # Create backup if file exists
            if create_backup and output_file.exists():
                DataStorage.backup(output_file)

            # Build complete data structure
            data = {
                "metadata": metadata or {},
                "practices": practices,
                "generated_at": datetime.now().isoformat(),
                "total_practices": len(practices),
            }

            # Add default metadata
            if "version" not in data["metadata"]:
                data["metadata"]["version"] = "2.0"
            if "source" not in data["metadata"]:
                data["metadata"]["source"] = "DPC Enrichment System V2"

            # Ensure parent directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write: write to temp file, then rename
            temp_file = output_file.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(output_file)

            # Log statistics
            file_size_mb = output_file.stat().st_size / 1024 / 1024
            logger.info(
                f"Saved {len(practices)} practices to {output_file.name} "
                f"({file_size_mb:.2f} MB)"
            )

        except Exception as e:
            logger.error(f"Failed to save enriched data: {e}")
            raise

    @staticmethod
    def load_enriched(input_file: Path) -> tuple[List[Dict], Dict]:
        """
        Load enriched practices from JSON file.

        Args:
            input_file: Input file path

        Returns:
            Tuple of (practices list, metadata dict)

        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If load fails
        """
        try:
            input_file = Path(input_file)

            if not input_file.exists():
                raise FileNotFoundError(f"File not found: {input_file}")

            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle both dict format (with metadata/practices keys) and legacy list format
            if isinstance(data, list):
                # Legacy format: file contains direct list of practices
                practices = data
                metadata = {}
                logger.warning(f"Loaded legacy format (bare list) from {input_file.name}")
            elif isinstance(data, dict):
                # Modern format: file contains dict with metadata and practices
                practices = data.get('practices', [])
                metadata = data.get('metadata', {})
            else:
                raise ValueError(f"Invalid data format in {input_file.name}: expected list or dict, got {type(data)}")

            logger.info(f"Loaded {len(practices)} practices from {input_file.name}")

            return practices, metadata

        except Exception as e:
            logger.error(f"Failed to load enriched data: {e}")
            raise

    @staticmethod
    def backup(file_path: Path, backup_dir: Optional[Path] = None):
        """
        Create backup of file.

        Args:
            file_path: File to backup
            backup_dir: Backup directory (default: file_path.parent / 'backups')
        """
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                logger.warning(f"Cannot backup non-existent file: {file_path}")
                return

            # Default backup directory
            if backup_dir is None:
                backup_dir = file_path.parent / 'backups'

            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create timestamped backup filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{file_path.stem}_BACKUP_{timestamp}{file_path.suffix}"
            backup_path = backup_dir / backup_name

            # Copy file
            shutil.copy2(file_path, backup_path)

            logger.info(f"Created backup: {backup_path.name}")

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            # Don't raise - backup failure shouldn't stop the process

    @staticmethod
    def merge_datasets(
        existing_file: Path,
        new_practices: List[Dict],
        merge_strategy: str = 'prefer_new'
    ) -> List[Dict]:
        """
        Merge new practices with existing dataset.

        Args:
            existing_file: Existing data file
            new_practices: New practices to merge
            merge_strategy: 'prefer_new', 'prefer_existing', or 'newest'

        Returns:
            Merged practices list
        """
        try:
            # Load existing data
            if existing_file.exists():
                existing_practices, _ = DataStorage.load_enriched(existing_file)
            else:
                existing_practices = []

            # Create lookup by practice_id
            existing_dict = {p['practice_id']: p for p in existing_practices}
            new_dict = {p['practice_id']: p for p in new_practices}

            # Merge based on strategy
            merged_dict = {}

            if merge_strategy == 'prefer_new':
                # Start with existing, overwrite with new
                merged_dict.update(existing_dict)
                merged_dict.update(new_dict)

            elif merge_strategy == 'prefer_existing':
                # Start with new, overwrite with existing
                merged_dict.update(new_dict)
                merged_dict.update(existing_dict)

            elif merge_strategy == 'newest':
                # Keep whichever has newest enrichment_v2_at
                merged_dict.update(existing_dict)

                for practice_id, new_practice in new_dict.items():
                    if practice_id not in merged_dict:
                        merged_dict[practice_id] = new_practice
                    else:
                        existing_time = existing_dict[practice_id].get('enriched_at', '')
                        new_time = new_practice.get('enriched_at', '')

                        if new_time > existing_time:
                            merged_dict[practice_id] = new_practice

            merged_practices = list(merged_dict.values())

            logger.info(
                f"Merged {len(existing_practices)} existing + {len(new_practices)} new = "
                f"{len(merged_practices)} total practices"
            )

            return merged_practices

        except Exception as e:
            logger.error(f"Merge failed: {e}")
            raise

    @staticmethod
    def get_dataset_stats(file_path: Path) -> Dict:
        """
        Get statistics about a dataset.

        Args:
            file_path: Data file path

        Returns:
            Statistics dict
        """
        try:
            practices, metadata = DataStorage.load_enriched(file_path)

            # Count statuses
            statuses = {}
            for practice in practices:
                status = practice.get('enrichment_status', 'unknown')
                statuses[status] = statuses.get(status, 0) + 1

            # Calculate costs
            total_cost = sum(
                practice.get('_enrichment_metadata', {}).get('llm_cost', 0)
                for practice in practices
            )

            file_size_mb = file_path.stat().st_size / 1024 / 1024

            return {
                'total_practices': len(practices),
                'status_breakdown': statuses,
                'total_cost': total_cost,
                'file_size_mb': file_size_mb,
                'metadata': metadata,
                'generated_at': metadata.get('generated_at'),
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
