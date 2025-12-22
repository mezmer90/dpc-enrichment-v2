"""
Field extractor with comprehensive prompt

Extracts 80+ structured fields from practice markdown content.
"""

import logging
from typing import Dict
from .gemini_client import GeminiClient

logger = logging.getLogger(__name__)


# Comprehensive extraction prompt for all 80+ fields
EXTRACTION_PROMPT = """You are extracting comprehensive data from a Direct Primary Care practice website.

**Practice:** {practice_name}
**Location:** {location_context}
**Website:** {website_url}
**ID:** {practice_id}

**IMPORTANT - MULTI-LOCATION AWARENESS:**
This practice may be part of a multi-location organization. The website may list providers and details for MULTIPLE locations.

**CRITICAL LOCATION-MATCHING RULES:**
1. **ONLY extract providers/staff who work at THIS specific location**: {location_context}
2. **ONLY extract office hours for THIS specific location**
3. **ONLY extract phone/contact info for THIS specific location**
4. **Shared data** (pricing, services, philosophy) can be the same across all locations
5. When provider info includes location context, ONLY include providers matching: {location_context}
6. If you cannot determine which providers work at this location, use empty list []
7. If multiple locations share the same phone/hours, extract the shared data

Below is the complete website content (multiple pages merged):

---
{markdown}
---

Extract ALL available information and return as JSON. For missing fields use "-NA-".

Return ONLY valid JSON (no markdown, no explanations):

{{
  "philosophy": "Complete practice philosophy/mission (150-500 chars)",
  "tagline": "Practice tagline or slogan",
  "mission_statement": "Formal mission statement if different from philosophy",
  "year_established": 2020,

  "providers": [
    {{
      "name": "Full name with credentials",
      "specialty": "Medical specialty",
      "bio": "Complete biography (200+ chars preferred)",
      "medical_school": "Medical school name and year",
      "residency": "Residency program",
      "board_certifications": ["Board Certification 1", "Board Certification 2"]
    }}
  ],
  "provider_count": 0,

  "services_offered": ["Service 1", "Service 2", "Service 3", ...],
  "procedures_offered": ["Procedure 1", "Minor surgery 2", ...],
  "lab_services": ["Lab test 1", "Blood work", "Urinalysis", ...],
  "imaging_services": ["X-ray", "Ultrasound", ...],

  "pricing_individual_monthly": 75.0,
  "pricing_individual_annual": 850.0,
  "pricing_family_monthly": 150.0,
  "pricing_family_annual": 1700.0,
  "pricing_child_monthly": 25.0,
  "pricing_senior_monthly": 100.0,
  "enrollment_fee": 50.0,
  "discounts_available": "Description of any discounts, promotions, or special pricing",

  "hours": "General hours description",
  "office_hours_monday": "9:00 AM - 5:00 PM",
  "office_hours_tuesday": "9:00 AM - 5:00 PM",
  "office_hours_wednesday": "9:00 AM - 5:00 PM",
  "office_hours_thursday": "9:00 AM - 5:00 PM",
  "office_hours_friday": "9:00 AM - 5:00 PM",
  "office_hours_saturday": "Closed",
  "office_hours_sunday": "Closed",
  "after_hours_access": true,
  "same_day_appointments": true,
  "average_visit_length": "30-45 minutes",

  "ages_accepted": "All ages",
  "ages_accepted_min": 0,
  "ages_accepted_max": 999,
  "accepting_patients": true,
  "languages_spoken": ["English", "Spanish"],

  "telehealth_available": true,
  "home_visits_available": false,
  "patient_portal_url": "https://portal.example.com",
  "online_booking_url": "https://book.example.com",

  "facebook_url": "https://facebook.com/...",
  "instagram_url": "https://instagram.com/...",
  "twitter_url": "https://twitter.com/...",
  "linkedin_url": "https://linkedin.com/...",
  "youtube_url": "https://youtube.com/...",
  "phone_alt": "Alternative phone number",
  "email": "contact@example.com",

  "insurance_alternatives": "Description of how they work with insurance companies or alternatives",
  "payment_methods": ["Credit Card", "ACH", "Check", "HSA", "FSA"],
  "testimonials": [
    {{
      "text": "Complete testimonial quote",
      "author": "Patient name or initials"
    }}
  ],
  "dba_names": ["Doing Business As names"],
  "additional_locations": [
    {{
      "address": "Street address",
      "city": "City",
      "state": "ST",
      "zip": "12345"
    }}
  ],
  "recent_blog_posts": [
    {{
      "title": "Blog post title",
      "url": "https://...",
      "date": "2024-01-15"
    }}
  ],

  "faq_1_question": "What is Direct Primary Care?",
  "faq_1_answer": "Complete answer to question 1",
  "faq_2_question": "How much does membership cost?",
  "faq_2_answer": "Complete answer to question 2",
  "faq_3_question": "What services are included?",
  "faq_3_answer": "Complete answer to question 3",
  "faq_4_question": "Do you accept insurance?",
  "faq_4_answer": "Complete answer to question 4",
  "faq_5_question": "How do I enroll?",
  "faq_5_answer": "Complete answer to question 5"
}}

**EXTRACTION GUIDELINES:**

**SHARED DATA (same across all locations):**
- Services offered, procedures, lab services, imaging services
- Pricing (membership fees, enrollment fees)
- Philosophy, mission statement, tagline
- Insurance alternatives, payment methods
- FAQs (general questions about DPC model)
- Telehealth availability
→ Extract these even if they appear to be shared across multiple locations

**LOCATION-SPECIFIC DATA (unique to THIS location: {location_context}):**
- **Providers/doctors/staff**: ONLY include those who work at THIS specific location
- **Office hours**: ONLY hours for THIS location
- **Phone numbers**: ONLY phone for THIS location (or shared number if same for all)
- **Languages spoken**: If varies by location, ONLY for THIS location
- **Testimonials**: Prefer testimonials mentioning THIS location
→ For these fields, carefully match the location context before extracting

**General Guidelines:**
1. Extract ALL available information - be comprehensive
2. For services: List ALL services mentioned (aim for 10-30 services)
3. For pricing: Look carefully for membership fees, enrollment fees, pricing tiers
4. For FAQs: Extract the 5 most relevant/common questions
5. For contact: Look for all social media, email, alternate phone
6. Use "-NA-" ONLY when information truly doesn't exist
7. For numeric fields use -1 if not found (not "-NA-")
8. For boolean fields: true/false based on explicit mentions
9. Return valid JSON only (no extra text)

**CRITICAL DATA ACCURACY RULES:**

**What YOU CAN DO (Reasonable Interpretation):**
✓ Interpret and infer information when there's clear context supporting it
✓ Standardize formats (e.g., "9am-5pm" → "9:00 AM - 5:00 PM")
✓ Derive obvious facts (e.g., if only adult services mentioned → ages_accepted_min: 18)
✓ Extract synonyms/equivalent info (e.g., "we see all ages" → ages_accepted: "All ages")
✓ Combine related info from multiple pages (e.g., pricing from different sections)
✓ Infer provider count from number of provider bios listed
✓ Extract services from descriptive text (e.g., "we treat diabetes" → "Diabetes Management")

**What YOU CANNOT DO (Fabrication/Hallucination):**
✗ NEVER invent pricing, phone numbers, addresses, or contact info not present in content
✗ NEVER create provider names, credentials, or bios that aren't explicitly mentioned
✗ NEVER fabricate services, procedures, or capabilities not described
✗ NEVER make up testimonials, FAQs, or quotes that don't exist in the content
✗ NEVER guess at office hours, ages accepted, or specific policies if not stated
✗ NEVER copy data from other practices or use "typical DPC practice" assumptions
✗ NEVER fill blanks with placeholder/example data
✗ NEVER lie, fabricate, or create information - this is a healthcare directory

**When in Doubt:**
- If information is clearly stated but needs interpretation: INTERPRET IT
- If information is vague or uncertain: Use "-NA-" for strings, -1 for numbers
- If you're unsure whether something is implied: Use "-NA-"/-1 (err on side of caution)

This data powers a critical healthcare directory. Accuracy is paramount. Be thorough, be smart about interpretation, but NEVER fabricate.
"""


class FieldExtractor:
    """
    Extracts structured fields from markdown content using AI.

    Handles prompt formatting, response parsing, and data validation.
    """

    def __init__(self, gemini_client: GeminiClient):
        """
        Initialize extractor.

        Args:
            gemini_client: GeminiClient instance for API calls
        """
        self.client = gemini_client

    async def extract(
        self,
        markdown: str,
        practice_data: Dict
    ) -> Dict:
        """
        Extract all fields from markdown.

        Args:
            markdown: Merged markdown content from all pages
            practice_data: Basic practice data (id, name, url, etc.)

        Returns:
            Extracted data dict with all fields

        Raises:
            Exception: If extraction fails
        """
        try:
            # Call Gemini for extraction
            extracted = await self.client.extract_data(
                markdown=markdown,
                practice_data=practice_data,
                prompt_template=EXTRACTION_PROMPT
            )

            # Validate and clean extracted data
            validated = self._validate_extracted_data(extracted, practice_data)

            # Sanitize practice name for console display
            practice_name = practice_data.get('practice_name', '')
            display_name = practice_name.encode('ascii', errors='replace').decode('ascii')

            logger.info(
                f"Extracted {len(validated)} fields for {display_name}"
            )

            return validated

        except Exception as e:
            logger.error(f"Field extraction failed for {practice_data.get('practice_id')}: {e}")
            raise

    def _validate_extracted_data(self, extracted: Dict, practice_data: Dict) -> Dict:
        """
        Validate and clean extracted data.

        Args:
            extracted: Raw extracted data from AI
            practice_data: Original practice data

        Returns:
            Validated and cleaned data
        """
        # Ensure required fields exist
        validated = extracted.copy()

        # Preserve original DPC Frontier fields (never overwrite with -NA-)
        preserve_fields = [
            'practice_id', 'practice_name', 'website_url', 'phone',
            'address_street', 'address_city', 'address_state', 'address_zip',
            'latitude', 'longitude', 'specialty', 'practice_type',
            'verified', 'accepting_patients'
        ]

        for field in preserve_fields:
            if field in practice_data and practice_data[field]:
                validated[field] = practice_data[field]

        # Clean up -NA- values for numeric fields
        numeric_fields = [
            'pricing_individual_monthly', 'pricing_individual_annual',
            'pricing_family_monthly', 'pricing_family_annual',
            'pricing_child_monthly', 'pricing_senior_monthly',
            'enrollment_fee', 'year_established',
            'ages_accepted_min', 'ages_accepted_max', 'provider_count'
        ]

        for field in numeric_fields:
            if field in validated:
                if validated[field] == "-NA-" or validated[field] is None:
                    validated[field] = -1
                elif isinstance(validated[field], str):
                    try:
                        validated[field] = float(validated[field])
                    except ValueError:
                        validated[field] = -1

        # Ensure lists are actually lists
        list_fields = [
            'providers', 'services_offered', 'procedures_offered',
            'lab_services', 'imaging_services', 'languages_spoken',
            'payment_methods', 'testimonials', 'dba_names',
            'additional_locations', 'recent_blog_posts'
        ]

        for field in list_fields:
            if field in validated:
                if not isinstance(validated[field], list):
                    validated[field] = []
            else:
                validated[field] = []

        # Count providers
        validated['provider_count'] = len(validated.get('providers', []))

        # Ensure booleans are actually booleans
        boolean_fields = [
            'telehealth_available', 'home_visits_available',
            'same_day_appointments', 'after_hours_access'
        ]

        for field in boolean_fields:
            if field in validated:
                if isinstance(validated[field], str):
                    validated[field] = validated[field].lower() in ('true', 'yes', '1')
                elif validated[field] is None:
                    validated[field] = False

        return validated

    def get_extraction_stats(self, extracted: Dict) -> Dict:
        """
        Get statistics about extracted data.

        Args:
            extracted: Extracted data dict

        Returns:
            Statistics dict
        """
        stats = {
            'total_fields': len(extracted),
            'fields_with_data': 0,
            'na_fields': 0,
            'providers_count': len(extracted.get('providers', [])),
            'services_count': len(extracted.get('services_offered', [])),
            'procedures_count': len(extracted.get('procedures_offered', [])),
            'faqs_count': 0,
        }

        # Count fields with actual data
        for key, value in extracted.items():
            if key.startswith('_'):
                continue  # Skip metadata fields

            if value == "-NA-" or value == -1:
                stats['na_fields'] += 1
            elif value:
                stats['fields_with_data'] += 1

        # Count FAQs
        for i in range(1, 6):
            q_key = f'faq_{i}_question'
            a_key = f'faq_{i}_answer'
            if extracted.get(q_key) and extracted.get(q_key) != "-NA-":
                stats['faqs_count'] += 1

        # Calculate coverage percentage
        stats['coverage_percent'] = (stats['fields_with_data'] / stats['total_fields']) * 100

        return stats
