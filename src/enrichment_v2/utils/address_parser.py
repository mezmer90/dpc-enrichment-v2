"""
Address Parser Utility

Parses addresses from Google Maps URLs to extract:
- Street address
- City
- State
- ZIP code
"""

import re
from urllib.parse import urlparse, parse_qs, unquote
from typing import Dict, Optional


def parse_address_from_google_maps(url: str) -> Dict[str, str]:
    """
    Parse address components from Google Maps URL.

    Args:
        url: Google Maps URL like:
             https://www.google.com/maps/search/?api=1&query=2851%20N%20Tenaya%20Way%2C%20Ste.%20203%2C%20Las%20Vegas%2C%20NV%2089128

    Returns:
        Dict with keys: street, city, state, zip
        Example: {
            'street': '2851 N Tenaya Way, Ste. 203',
            'city': 'Las Vegas',
            'state': 'NV',
            'zip': '89128'
        }
    """
    result = {
        'address_street': '',
        'address_city': '',
        'address_state': '',
        'address_zip': ''
    }

    if not url or 'google.com/maps' not in url:
        return result

    try:
        # Parse URL and extract query parameter
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        if 'query' not in params:
            return result

        # Get address from query parameter and decode
        address = unquote(params['query'][0])

        # Address format: "Street, City, State ZIP"
        # Example: "2851 N Tenaya Way, Ste. 203, Las Vegas, NV 89128"

        # Split by comma
        parts = [p.strip() for p in address.split(',')]

        if len(parts) < 2:
            return result

        # Last part typically has: "State ZIP"
        last_part = parts[-1].strip()

        # Extract ZIP code (5 digits)
        zip_match = re.search(r'\b(\d{5})\b', last_part)
        if zip_match:
            result['address_zip'] = zip_match.group(1)
            # Remove ZIP from last part
            last_part = last_part.replace(zip_match.group(1), '').strip()

        # Extract state (2 letters, uppercase)
        state_match = re.search(r'\b([A-Z]{2})\b', last_part)
        if state_match:
            result['address_state'] = state_match.group(1)
            # Remove state from last part
            last_part = last_part.replace(state_match.group(1), '').strip()

        # If last part still has content after removing state/zip, it might be part of city
        if last_part and not state_match:
            # It's probably the city
            result['address_city'] = last_part
        elif len(parts) >= 2:
            # Second to last is typically the city
            result['address_city'] = parts[-2].strip()

        # Everything before city is street address
        if result['address_city']:
            # Find where city starts
            city_index = parts.index(result['address_city'])
            if city_index > 0:
                result['address_street'] = ', '.join(parts[:city_index])
        elif len(parts) > 1:
            # No city found, first parts are street
            result['address_street'] = ', '.join(parts[:-1])

    except Exception as e:
        # If parsing fails, return empty dict
        pass

    return result


def enrich_practice_with_address(practice: Dict) -> Dict:
    """
    Enrich practice data with parsed address components.

    Args:
        practice: Practice dict with google_maps_url

    Returns:
        Practice dict with added address_street, address_city, address_state, address_zip
    """
    if not practice.get('google_maps_url'):
        return practice

    # Parse address from Google Maps URL
    address_parts = parse_address_from_google_maps(practice['google_maps_url'])

    # Add to practice data (don't overwrite if already exists)
    for key, value in address_parts.items():
        if value and not practice.get(key):
            practice[key] = value

    return practice
