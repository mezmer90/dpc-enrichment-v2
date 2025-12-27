"""
Load practice data from JSON file into PostgreSQL database

This script loads the DPC practice data from the JSON file into the PostgreSQL database
on Railway. It can be run locally or via Railway CLI.

Usage:
    # Local (with DATABASE_URL set)
    python load_practices.py

    # Via Railway CLI
    railway run python load_practices.py
"""

import os
import json
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add webapp directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp.models import Practice


def load_practices_from_json(json_file, database_url, skip_existing=True):
    """
    Load practices from JSON file into database

    Args:
        json_file: Path to JSON file
        database_url: PostgreSQL database URL
        skip_existing: If True, skip practices that already exist in database
    """
    # Fix postgres:// to postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    # Create engine and session
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    print(f"Loading practices from {json_file}...")

    # Load JSON data
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    practices_data = data.get('practices', [])
    metadata = data.get('metadata', {})

    print(f"Found {len(practices_data)} practices in JSON file")
    print(f"Metadata: {metadata}")

    # Check existing practices
    existing_ids = set()
    if skip_existing:
        existing_practices = session.query(Practice.practice_id).all()
        existing_ids = {p.practice_id for p in existing_practices}
        print(f"Found {len(existing_ids)} existing practices in database")

    # Statistics
    stats = {
        'total': len(practices_data),
        'added': 0,
        'skipped': 0,
        'errors': 0
    }

    # Load practices
    print("\nLoading practices into database...")

    for practice_data in tqdm(practices_data, desc="Loading practices"):
        practice_id = practice_data.get('practice_id')

        if not practice_id:
            print(f"Warning: Practice missing practice_id, skipping: {practice_data.get('practice_name')}")
            stats['errors'] += 1
            continue

        # Skip if already exists
        if skip_existing and practice_id in existing_ids:
            stats['skipped'] += 1
            continue

        try:
            # Create Practice instance
            practice = Practice(
                practice_id=practice_id,
                practice_name=practice_data.get('practice_name'),
                website_url=practice_data.get('website_url'),

                # Address
                address_street=practice_data.get('address_street'),
                address_city=practice_data.get('address_city'),
                address_state=practice_data.get('address_state'),
                address_zip=practice_data.get('address_zip'),

                # Contact
                phone=practice_data.get('phone'),
                latitude=practice_data.get('latitude'),
                longitude=practice_data.get('longitude'),

                # Enrichment status
                enrichment_status='pending',

                # Store full JSON data
                data=practice_data,

                # Timestamps
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            session.add(practice)
            stats['added'] += 1

            # Commit every 100 practices to avoid memory issues
            if stats['added'] % 100 == 0:
                session.commit()

        except Exception as e:
            print(f"\nError loading practice {practice_id}: {e}")
            stats['errors'] += 1
            session.rollback()
            continue

    # Final commit
    try:
        session.commit()
        print("\n✓ Successfully committed all changes")
    except Exception as e:
        print(f"\n✗ Error committing final changes: {e}")
        session.rollback()

    # Print statistics
    print("\n" + "="*60)
    print("LOADING COMPLETE")
    print("="*60)
    print(f"Total practices in file: {stats['total']}")
    print(f"Added to database:       {stats['added']}")
    print(f"Skipped (existing):      {stats['skipped']}")
    print(f"Errors:                  {stats['errors']}")
    print("="*60)

    # Verify database count
    total_in_db = session.query(Practice).count()
    print(f"\nTotal practices now in database: {total_in_db}")

    session.close()
    return stats


def main():
    """Main entry point"""
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("Error: DATABASE_URL environment variable not set")
        print("\nUsage:")
        print("  Local:  export DATABASE_URL='postgresql://...' && python load_practices.py")
        print("  Railway: railway run python load_practices.py")
        sys.exit(1)

    # JSON file path
    json_file = os.path.join(
        os.path.dirname(__file__),
        'dpc_complete_2763_practices_with_corrected_urls.json'
    )

    if not os.path.exists(json_file):
        print(f"Error: JSON file not found: {json_file}")
        sys.exit(1)

    # Load practices
    try:
        stats = load_practices_from_json(json_file, database_url, skip_existing=True)

        if stats['errors'] > 0:
            print(f"\n⚠ Warning: {stats['errors']} practices failed to load")
            sys.exit(1)
        else:
            print("\n✓ All practices loaded successfully!")
            sys.exit(0)

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
