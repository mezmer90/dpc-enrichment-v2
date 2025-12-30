"""
Fix malformed URLs in the database.

Common issues:
- Commas instead of periods (www.example,com -> www.example.com)
- Missing protocols (example.com -> https://example.com)
- Missing TLDs (medicaldojo -> likely medicaldojo.com)
- Extra whitespace
- Invalid characters
"""

import os
import re
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from webapp.models import Practice

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///dpc_enrichment.db')
# Handle Railway's postgres:// -> postgresql://
DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')

# Create database connection
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def is_valid_url(url):
    """Check if URL has basic valid structure."""
    if not url:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def fix_url(url):
    """
    Fix common URL problems.

    Returns:
        tuple: (fixed_url, list_of_fixes_applied, should_skip)
        should_skip=True means the URL is invalid and should be set to NULL
    """
    if not url:
        return None, [], True

    fixes_applied = []
    original_url = url

    # Strip whitespace
    url = url.strip()
    if url != original_url:
        fixes_applied.append("Stripped whitespace")

    # Check for placeholder URLs that should be NULL
    # Extract just the domain for checking
    domain_to_check = url.replace('https://', '').replace('http://', '').split('/')[0].lower()

    # Only match EXACT placeholder patterns, not substrings
    if domain_to_check in ['na', 'n/a', 'none', 'unknown', 'tbd', 'example.com', 'test.com', 'website.com']:
        return None, ["Invalid placeholder URL - should be NULL"], True

    # Check for "no website" in the domain
    if 'no%20website' in domain_to_check or domain_to_check == 'no website':
        return None, ["Invalid placeholder URL - should be NULL"], True

    # Fix comma instead of period in domain (www.example,com -> www.example.com)
    if ',' in url:
        # Check if comma is in domain part (not in query string)
        domain_part = url.split('?')[0]
        if ',' in domain_part:
            url = url.replace(',', '.')
            fixes_applied.append("Fixed comma -> period")

    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        fixes_applied.append("Added https:// protocol")

    # Parse the URL
    parsed = urlparse(url)

    # Check if domain has a TLD
    domain = parsed.netloc or parsed.path.split('/')[0]

    # Remove trailing slashes for domain check
    domain = domain.rstrip('/')

    # Check if domain has a TLD (has at least one dot)
    if domain and '.' not in domain:
        # Missing TLD - only add .com for reasonable domain names (length > 3)
        if len(domain) > 3:
            if parsed.netloc:
                url = f"{parsed.scheme}://{domain}.com{parsed.path}"
            else:
                url = f"{parsed.scheme}://{domain}.com"
            fixes_applied.append("Added .com TLD")
        else:
            # Very short domain, likely invalid
            return None, ["Domain too short - likely invalid"], True

    # Remove duplicate slashes in path (but not in protocol)
    if '//' in url.replace('https://', '').replace('http://', ''):
        parts = url.split('://')
        if len(parts) == 2:
            protocol, rest = parts
            rest = re.sub(r'/+', '/', rest)
            url = f"{protocol}://{rest}"
            fixes_applied.append("Fixed duplicate slashes")

    return url, fixes_applied, False


def scan_and_fix_urls(auto_confirm=False):
    """Scan database for malformed URLs and fix them."""

    session = Session()

    try:
        # Get all practices
        practices = session.query(Practice).all()

        total = len(practices)
        fixed_count = 0
        nulled_count = 0
        issues_found = []

        print(f"\nScanning {total} practices for URL issues...\n")

        for practice in practices:
            if not practice.website_url:
                continue

            original_url = practice.website_url
            fixed_url, fixes, should_null = fix_url(original_url)

            if fixes:
                issues_found.append({
                    'practice_id': practice.practice_id,
                    'practice_name': practice.practice_name,
                    'original_url': original_url,
                    'fixed_url': fixed_url,
                    'fixes': fixes,
                    'should_null': should_null
                })

                # Update the database
                if should_null:
                    practice.website_url = None
                    nulled_count += 1
                else:
                    practice.website_url = fixed_url
                    fixed_count += 1

        # Print findings
        if issues_found:
            print(f"Found {len(issues_found)} URLs with issues:\n")
            print("=" * 100)

            for issue in issues_found:
                print(f"\nPractice: {issue['practice_name']} ({issue['practice_id']})")
                print(f"Original: {issue['original_url']}")
                if issue['should_null']:
                    print(f"Action:   Set to NULL (invalid placeholder)")
                else:
                    print(f"Fixed:    {issue['fixed_url']}")
                print(f"Reason:   {', '.join(issue['fixes'])}")
                print("-" * 100)

            # Ask for confirmation or auto-confirm
            print(f"\n\nReady to update {fixed_count} URLs and set {nulled_count} to NULL in the database.")

            if auto_confirm:
                print("Auto-confirming changes...")
                confirm = 'yes'
            else:
                confirm = input("Proceed with updates? (yes/no): ").strip().lower()

            if confirm == 'yes':
                session.commit()
                print(f"\nSuccessfully updated {fixed_count} URLs and set {nulled_count} to NULL!")
            else:
                session.rollback()
                print("\nUpdates cancelled. No changes made.")
        else:
            print("No URL issues found! All URLs look good.")

    except Exception as e:
        print(f"\nError: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def check_invalid_urls():
    """Check for URLs that are clearly invalid or dead."""

    session = Session()

    try:
        practices = session.query(Practice).all()

        invalid_urls = []

        for practice in practices:
            if not practice.website_url:
                continue

            url = practice.website_url.lower()

            # Check for obviously invalid patterns
            if any([
                'example.com' in url,
                'test.com' in url,
                'localhost' in url,
                url.startswith('http://http'),
                url.startswith('https://https'),
            ]):
                invalid_urls.append({
                    'practice_id': practice.practice_id,
                    'practice_name': practice.practice_name,
                    'url': practice.website_url,
                    'reason': 'Clearly invalid URL pattern'
                })

        if invalid_urls:
            print(f"\nWarning: Found {len(invalid_urls)} potentially invalid URLs:\n")
            for item in invalid_urls:
                print(f"Practice: {item['practice_name']} ({item['practice_id']})")
                print(f"URL: {item['url']}")
                print(f"Reason: {item['reason']}\n")
        else:
            print("No obviously invalid URLs found.")

    finally:
        session.close()


if __name__ == '__main__':
    import sys

    # Check for --yes flag
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv

    print("=" * 100)
    print("DPC Practice URL Fixer")
    print("=" * 100)

    # Step 1: Scan and fix common issues
    scan_and_fix_urls(auto_confirm=auto_confirm)

    print("\n" + "=" * 100)
    print("Checking for obviously invalid URLs...")
    print("=" * 100)

    # Step 2: Check for invalid URLs
    check_invalid_urls()
