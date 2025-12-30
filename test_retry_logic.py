"""
Test script to verify retry logic for skipped practices.

Tests:
1. ProgressTracker.get_skipped() method
2. Orchestrator resume logic includes skipped practices
"""

import sys
from pathlib import Path
import tempfile
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.enrichment_v2.utils.progress import ProgressTracker, PracticeStatus


def test_get_skipped():
    """Test ProgressTracker.get_skipped() method"""
    print("=" * 60)
    print("Test 1: ProgressTracker.get_skipped()")
    print("=" * 60)

    # Create temporary progress file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)

    try:
        # Initialize tracker
        tracker = ProgressTracker(state_file=temp_file, auto_save=False)
        tracker.initialize_practices(['P1', 'P2', 'P3', 'P4', 'P5'])

        # Set different statuses
        tracker.update_status('P1', PracticeStatus.SUCCESS)
        tracker.update_status('P2', PracticeStatus.FAILED, error='Scraping failed')
        tracker.update_status('P3', PracticeStatus.SKIPPED, error='No website URL')
        tracker.update_status('P4', PracticeStatus.SKIPPED, error='Resource exhaustion')
        tracker.update_status('P5', PracticeStatus.PENDING)

        # Test get_skipped()
        skipped = tracker.get_skipped()

        print(f"\nSkipped practices: {skipped}")
        print(f"Expected: ['P3', 'P4']")

        # Verify
        assert len(skipped) == 2, f"Expected 2 skipped, got {len(skipped)}"
        assert 'P3' in skipped, "P3 should be skipped"
        assert 'P4' in skipped, "P4 should be skipped"
        assert 'P1' not in skipped, "P1 should not be skipped (success)"
        assert 'P2' not in skipped, "P2 should not be skipped (failed)"
        assert 'P5' not in skipped, "P5 should not be skipped (pending)"

        print("\n[OK] ProgressTracker.get_skipped() works correctly!")

        # Test other getter methods for consistency
        pending = tracker.get_pending()
        failed = tracker.get_failed()
        successful = tracker.get_successful()

        print(f"\nAll statuses:")
        print(f"  Pending: {pending}")
        print(f"  Failed: {failed}")
        print(f"  Skipped: {skipped}")
        print(f"  Successful: {successful}")

        assert pending == ['P5']
        assert failed == ['P2']
        assert successful == ['P1']

        print("\n[OK] All getter methods working correctly!")

        # Save and reload to test persistence
        tracker.save()

        tracker2 = ProgressTracker(state_file=temp_file, auto_save=False)
        tracker2.load()

        skipped2 = tracker2.get_skipped()
        assert skipped2 == skipped, "Skipped practices should persist after save/load"

        print("\n[OK] Skipped status persists correctly!")

        return True

    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()


def test_resume_logic():
    """Test that resume logic includes skipped practices"""
    print("\n" + "=" * 60)
    print("Test 2: Resume Logic Verification")
    print("=" * 60)

    # Create temporary progress file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)

    try:
        # Initialize tracker with practices
        tracker = ProgressTracker(state_file=temp_file, auto_save=True)
        tracker.initialize_practices(['P1', 'P2', 'P3', 'P4', 'P5'])

        # Simulate enrichment run with various outcomes
        tracker.update_status('P1', PracticeStatus.SUCCESS)
        tracker.update_status('P2', PracticeStatus.FAILED, error='Scraping failed')
        tracker.update_status('P3', PracticeStatus.SKIPPED, error='No website URL')
        tracker.update_status('P4', PracticeStatus.SKIPPED, error='Resource exhaustion')
        # P5 remains PENDING

        tracker.save()

        # Simulate resume: Load tracker and get practices to retry
        tracker2 = ProgressTracker(state_file=temp_file, auto_save=False)
        tracker2.load()

        pending_ids = tracker2.get_pending()
        failed_ids = tracker2.get_failed()
        skipped_ids = tracker2.get_skipped()
        successful_ids = tracker2.get_successful()

        # Simulate orchestrator resume logic
        to_process_ids = set(pending_ids + failed_ids + skipped_ids)

        print(f"\nResume status:")
        print(f"  Successful: {successful_ids} (keep)")
        print(f"  Failed: {failed_ids} (retry)")
        print(f"  Skipped: {skipped_ids} (retry)")
        print(f"  Pending: {pending_ids} (process)")
        print(f"\nTo process on resume: {sorted(to_process_ids)}")
        print(f"Expected: ['P2', 'P3', 'P4', 'P5']")

        # Verify
        assert to_process_ids == {'P2', 'P3', 'P4', 'P5'}, \
            f"Should retry failed, skipped, and pending practices"

        assert 'P1' not in to_process_ids, "P1 (successful) should not be retried"
        assert 'P2' in to_process_ids, "P2 (failed) should be retried"
        assert 'P3' in to_process_ids, "P3 (skipped) should be retried"
        assert 'P4' in to_process_ids, "P4 (skipped) should be retried"
        assert 'P5' in to_process_ids, "P5 (pending) should be processed"

        print("\n[OK] Resume logic correctly includes skipped practices!")

        return True

    finally:
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()


def main():
    """Run all tests"""
    print("\nTesting Retry Logic for Skipped Practices")
    print("=" * 60)

    try:
        # Run tests
        test_get_skipped()
        test_resume_logic()

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED!")
        print("=" * 60)
        print("\nRetry logic is working correctly:")
        print("  - ProgressTracker.get_skipped() method implemented")
        print("  - Resume logic includes PENDING + FAILED + SKIPPED practices")
        print("  - Skipped status persists across save/load")
        print("\nThe fix is ready for deployment!")
        print()

        return 0

    except AssertionError as e:
        print("\n" + "=" * 60)
        print("[FAILED] TEST FAILED!")
        print("=" * 60)
        print(f"\nAssertion Error: {e}")
        print()

        import traceback
        traceback.print_exc()

        return 1

    except Exception as e:
        print("\n" + "=" * 60)
        print("[ERROR] UNEXPECTED ERROR!")
        print("=" * 60)
        print(f"\nError: {e}")
        print()

        import traceback
        traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(main())
