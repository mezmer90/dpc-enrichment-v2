"""
Setup Validation Script

Tests your environment setup and API credentials before running enrichment.
Run this before starting the full enrichment to catch issues early.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load .env file
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        print("[OK] Loaded .env file")
    else:
        print("[!] WARNING: No .env file found")
        print("    Create one by copying .env.example to .env")
except ImportError:
    print("[!] python-dotenv not installed")
    print("    Install with: pip install python-dotenv")


def test_console_encoding():
    """Test Windows console encoding"""
    print("\n" + "=" * 60)
    print("TEST 1: Windows Console Encoding")
    print("=" * 60)

    try:
        from enrichment_v2.utils.safe_console import sanitize_for_console

        test_strings = [
            "Plain ASCII text",
            "Practice: Cafe Medical",
            "Status: [OK] Complete",
        ]

        print("\nTesting console encoding:")
        for text in test_strings:
            safe_text = sanitize_for_console(text)
            print(f"  {safe_text}")

        print("\n[OK] Console encoding working correctly")
        return True

    except Exception as e:
        print(f"\n[FAIL] Console encoding test failed: {e}")
        return False


def test_api_keys():
    """Test API keys are set"""
    print("\n" + "=" * 60)
    print("TEST 2: API Keys")
    print("=" * 60)

    try:
        from enrichment_v2.config import OPENROUTER_API_KEY, SCRAPERAPI_KEY

        all_good = True

        # Check OpenRouter
        if OPENROUTER_API_KEY:
            print(f"[OK] OPENROUTER_API_KEY set (length: {len(OPENROUTER_API_KEY)})")
        else:
            print("[FAIL] OPENROUTER_API_KEY not set!")
            print("       Set it in your .env file")
            all_good = False

        # Check ScraperAPI
        if SCRAPERAPI_KEY:
            print(f"[OK] SCRAPERAPI_KEY set (length: {len(SCRAPERAPI_KEY)})")
        else:
            print("[FAIL] SCRAPERAPI_KEY not set!")
            print("       Set it in your .env file")
            all_good = False

        return all_good

    except Exception as e:
        print(f"[FAIL] API key check failed: {e}")
        return False


def test_file_structure():
    """Test required files exist"""
    print("\n" + "=" * 60)
    print("TEST 3: File Structure")
    print("=" * 60)

    base_dir = Path(__file__).parent

    required_files = [
        'batch_enrich_v2.py',
        'src/enrichment_v2/config.py',
        'src/enrichment_v2/orchestrator.py',
        'src/enrichment_v2/utils/safe_console.py',
        'src/enrichment_v2/utils/api_exceptions.py',
        'src/enrichment_v2/utils/api_pause_handler.py',
        '.env.example',
        '.gitignore',
    ]

    all_good = True
    for file_path in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"[OK] {file_path}")
        else:
            print(f"[FAIL] {file_path} - NOT FOUND")
            all_good = False

    return all_good


def test_input_data():
    """Test input data file exists"""
    print("\n" + "=" * 60)
    print("TEST 4: Input Data")
    print("=" * 60)

    try:
        from enrichment_v2.config import INPUT_FILE
        from enrichment_v2.storage.data_storage import DataStorage

        if not INPUT_FILE.exists():
            print(f"[FAIL] Input file not found: {INPUT_FILE}")
            return False

        print(f"[OK] Input file exists: {INPUT_FILE.name}")

        # Try to load it
        practices, metadata = DataStorage.load_enriched(INPUT_FILE)
        print(f"[OK] Loaded {len(practices)} practices")

        return True

    except Exception as e:
        print(f"[FAIL] Input data test failed: {e}")
        return False


def test_imports():
    """Test all critical imports work"""
    print("\n" + "=" * 60)
    print("TEST 5: Python Imports")
    print("=" * 60)

    modules = [
        ('aiohttp', 'aiohttp'),
        ('playwright', 'playwright.async_api'),
        ('BeautifulSoup', 'bs4'),
        ('OpenAI client', 'openai'),
        ('trafilatura', 'trafilatura'),
        ('dotenv', 'dotenv'),
    ]

    all_good = True
    for name, module_path in modules:
        try:
            __import__(module_path)
            print(f"[OK] {name}")
        except ImportError as e:
            print(f"[FAIL] {name} - {e}")
            all_good = False

    return all_good


def main():
    """Run all validation tests"""
    print("\n" + "=" * 60)
    print("DPC ENRICHMENT V2 - SETUP VALIDATION")
    print("=" * 60)
    print("\nThis script validates your setup before running enrichment.")
    print("All tests should show [OK] for successful enrichment.\n")

    results = []

    # Run tests
    results.append(("Console Encoding", test_console_encoding()))
    results.append(("API Keys", test_api_keys()))
    results.append(("File Structure", test_file_structure()))
    results.append(("Input Data", test_input_data()))
    results.append(("Python Imports", test_imports()))

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"{status:15} - {test_name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)

    if all_passed:
        print("[OK] ALL TESTS PASSED!")
        print("=" * 60)
        print("\nYour setup is ready for enrichment.")
        print("\nNext steps:")
        print("  1. Run test: python batch_enrich_v2.py --limit 5")
        print("  2. Run full:  python batch_enrich_v2.py")
        print("\n" + "=" * 60)
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED")
        print("=" * 60)
        print("\nPlease fix the failed tests before running enrichment.")
        print("See error messages above for details.")
        print("\n" + "=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
