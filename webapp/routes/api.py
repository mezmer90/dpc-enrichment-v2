"""
REST API routes for enrichment control
"""

from flask import Blueprint, jsonify, request, Response, send_file
from webapp.models import EnrichmentRun, Practice, APIStatus
from webapp.services.progress_service import set_run_control
from webapp.extensions import db
import json
import csv
from io import StringIO, BytesIO
from datetime import datetime

bp = Blueprint('api', __name__)


@bp.route('/enrichment/start', methods=['POST'])
def start_enrichment():
    """Start new enrichment run"""
    try:
        # Check if already running
        existing_run = EnrichmentRun.query.filter(
            EnrichmentRun.status.in_(['running', 'paused'])
        ).first()

        if existing_run:
            return jsonify({
                'error': 'Enrichment already running',
                'run_id': existing_run.id
            }), 400

        # Get parameters
        data = request.get_json() or {}
        limit = data.get('limit')
        max_workers = data.get('max_workers', 6)
        retry_statuses = data.get('retry_statuses', ['pending', 'failed', 'skipped'])

        # Validate retry_statuses
        VALID_STATUSES = ['pending', 'failed', 'skipped']
        if not isinstance(retry_statuses, list) or not retry_statuses:
            return jsonify({'error': 'retry_statuses must be a non-empty list'}), 400

        invalid = [s for s in retry_statuses if s not in VALID_STATUSES]
        if invalid:
            return jsonify({'error': f'Invalid statuses: {invalid}'}), 400

        # Create new run
        run = EnrichmentRun(
            status='pending',
            created_by='admin',
            config={
                'limit': limit,
                'max_workers': max_workers,
                'retry_statuses': retry_statuses
            }
        )
        db.session.add(run)
        db.session.commit()

        # Start background task
        from webapp.tasks.enrichment_task import enrich_practices_task
        task = enrich_practices_task.delay(run.id, limit=limit, max_workers=max_workers, retry_statuses=retry_statuses)

        # Update run with task ID
        run.config['celery_task_id'] = task.id
        db.session.commit()

        return jsonify({
            'success': True,
            'run_id': run.id,
            'task_id': task.id,
            'status': 'started'
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({
            'error': f'Failed to start enrichment: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500


@bp.route('/enrichment/pause', methods=['POST'])
def pause_enrichment():
    """Pause running enrichment"""

    current_run = EnrichmentRun.query.filter_by(status='running').first()

    if not current_run:
        return jsonify({'error': 'No running enrichment found'}), 404

    # Set pause control flag in Redis
    set_run_control(current_run.id, 'pause')

    # Update database status
    current_run.status = 'paused'
    db.session.commit()

    return jsonify({
        'success': True,
        'run_id': current_run.id,
        'status': 'paused'
    })


@bp.route('/enrichment/resume', methods=['POST'])
def resume_enrichment():
    """Resume paused enrichment"""

    paused_run = EnrichmentRun.query.filter_by(status='paused').first()

    if not paused_run:
        return jsonify({'error': 'No paused enrichment found'}), 404

    # Set resume control flag in Redis
    set_run_control(paused_run.id, 'resume')

    # Update database status
    paused_run.status = 'running'
    db.session.commit()

    return jsonify({
        'success': True,
        'run_id': paused_run.id,
        'status': 'resumed'
    })


@bp.route('/enrichment/stop', methods=['POST'])
def stop_enrichment():
    """Stop running enrichment"""

    current_run = EnrichmentRun.query.filter(
        EnrichmentRun.status.in_(['running', 'paused'])
    ).first()

    if not current_run:
        return jsonify({'error': 'No running enrichment found'}), 404

    # Set stop control flag in Redis
    set_run_control(current_run.id, 'stop')

    # Update database status
    current_run.status = 'stopped'
    current_run.completed_at = db.func.now()
    db.session.commit()

    return jsonify({
        'success': True,
        'run_id': current_run.id,
        'status': 'stopped'
    })


@bp.route('/enrichment/status', methods=['GET'])
def get_status():
    """Get current enrichment status"""

    current_run = EnrichmentRun.query.filter(
        EnrichmentRun.status.in_(['running', 'paused'])
    ).first()

    if not current_run:
        return jsonify({
            'status': 'idle',
            'current_run': None
        })

    # Get cached stats from Redis (updated in real-time during enrichment)
    from webapp.services.progress_service import get_current_stats
    cached_stats = get_current_stats(current_run.id)

    # Use cached stats if available (for running enrichment), otherwise use database
    if cached_stats and cached_stats.get('total_practices', 0) > 0:
        # Parse total_cost from formatted string (e.g., "$0.00")
        total_cost_str = cached_stats.get('total_cost', '$0.00')
        if isinstance(total_cost_str, str):
            total_cost = float(total_cost_str.replace('$', '').replace(',', ''))
        else:
            total_cost = float(total_cost_str)

        # Parse success_rate from formatted string (e.g., "50.0%")
        success_rate_str = cached_stats.get('success_rate', '0.0%')
        if isinstance(success_rate_str, str):
            success_rate = float(success_rate_str.replace('%', ''))
        else:
            success_rate = float(success_rate_str)

        # Use real-time cached stats
        return jsonify({
            'status': current_run.status,
            'current_run': {
                'id': current_run.id,
                'status': current_run.status,
                'total_practices': cached_stats.get('total_practices', 0),
                'successful': cached_stats.get('successful', 0),
                'failed': cached_stats.get('failed', 0),
                'skipped': cached_stats.get('skipped', 0),
                'success_rate': success_rate,
                'total_cost': total_cost,
                'started_at': current_run.started_at.isoformat() if current_run.started_at else None
            }
        })
    else:
        # Fallback to database stats
        return jsonify({
            'status': current_run.status,
            'current_run': {
                'id': current_run.id,
                'status': current_run.status,
                'total_practices': current_run.total_practices,
                'successful': current_run.successful,
                'failed': current_run.failed,
                'skipped': current_run.skipped,
                'success_rate': current_run.success_rate,
                'total_cost': float(current_run.total_cost or 0),
                'started_at': current_run.started_at.isoformat() if current_run.started_at else None
            }
        })


@bp.route('/enrichment/progress/stream', methods=['GET'])
def progress_stream():
    """Server-Sent Events stream for real-time progress"""

    def generate():
        # Import here to avoid circular import
        from webapp.services.progress_service import subscribe_to_progress

        for update in subscribe_to_progress():
            yield f"data: {json.dumps(update)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@bp.route('/practices', methods=['GET'])
def list_practices():
    """List practices with filtering"""

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status')
    search = request.args.get('search')

    query = Practice.query

    if status:
        query = query.filter_by(enrichment_status=status)

    if search:
        query = query.filter(
            db.or_(
                Practice.practice_name.ilike(f'%{search}%'),
                Practice.practice_id.ilike(f'%{search}%')
            )
        )

    practices_paginated = query.order_by(
        Practice.updated_at.desc()
    ).paginate(page=page, per_page=per_page)

    return jsonify({
        'practices': [
            {
                'id': p.id,
                'practice_id': p.practice_id,
                'practice_name': p.practice_name,
                'website_url': p.website_url,
                'enrichment_status': p.enrichment_status,
                'enriched_at': p.enriched_at.isoformat() if p.enriched_at else None
            }
            for p in practices_paginated.items
        ],
        'pagination': {
            'page': practices_paginated.page,
            'per_page': practices_paginated.per_page,
            'total': practices_paginated.total,
            'pages': practices_paginated.pages
        }
    })


@bp.route('/practices/<int:practice_id>', methods=['GET'])
def get_practice(practice_id):
    """Get single practice details"""

    practice = Practice.query.get_or_404(practice_id)

    return jsonify({
        'id': practice.id,
        'practice_id': practice.practice_id,
        'practice_name': practice.practice_name,
        'website_url': practice.website_url,
        'address': {
            'street': practice.address_street,
            'city': practice.address_city,
            'state': practice.address_state,
            'zip': practice.address_zip
        },
        'phone': practice.phone,
        'enrichment_status': practice.enrichment_status,
        'enriched_at': practice.enriched_at.isoformat() if practice.enriched_at else None,
        'data': practice.data
    })


@bp.route('/api_status', methods=['GET'])
def get_api_status():
    """Get API health status"""

    statuses = APIStatus.query.all()

    return jsonify({
        'apis': [
            {
                'name': s.api_name,
                'status': s.status,
                'healthy': s.is_healthy,
                'last_error': s.last_error,
                'updated_at': s.updated_at.isoformat()
            }
            for s in statuses
        ]
    })


@bp.route('/stats', methods=['GET'])
def get_stats():
    """Get overall statistics"""

    total_practices = Practice.query.count()
    completed = Practice.query.filter_by(enrichment_status='completed').count()
    failed = Practice.query.filter_by(enrichment_status='failed').count()
    pending = Practice.query.filter_by(enrichment_status='pending').count()
    skipped = Practice.query.filter_by(enrichment_status='skipped').count()

    total_cost = db.session.query(
        db.func.sum(EnrichmentRun.total_cost)
    ).scalar() or 0

    return jsonify({
        'total_practices': total_practices,
        'completed': completed,
        'failed': failed,
        'pending': pending,
        'skipped': skipped,
        'success_rate': (completed / total_practices * 100) if total_practices > 0 else 0,
        'total_cost': float(total_cost),
        'total_runs': EnrichmentRun.query.count()
    })


@bp.route('/export/csv', methods=['GET'])
def export_csv():
    """Export practices to CSV"""

    # Get filter parameters
    status = request.args.get('status')
    search = request.args.get('search')

    # Build query
    query = Practice.query

    if status:
        query = query.filter_by(enrichment_status=status)

    if search:
        query = query.filter(
            db.or_(
                Practice.practice_name.ilike(f'%{search}%'),
                Practice.practice_id.ilike(f'%{search}%')
            )
        )

    practices = query.all()

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'Practice ID',
        'Practice Name',
        'Website URL',
        'Street Address',
        'City',
        'State',
        'ZIP',
        'Phone',
        'Enrichment Status',
        'Enriched At',
        'Field Count',
        'Has Data'
    ])

    # Write rows
    for p in practices:
        field_count = 0
        if p.data:
            field_count = sum(
                1 for k, v in p.data.items()
                if not k.startswith('_') and v not in (None, '', [], {})
            )

        writer.writerow([
            p.practice_id,
            p.practice_name or '',
            p.website_url or '',
            p.address_street or '',
            p.address_city or '',
            p.address_state or '',
            p.address_zip or '',
            p.phone or '',
            p.enrichment_status,
            p.enriched_at.isoformat() if p.enriched_at else '',
            field_count,
            'Yes' if p.data else 'No'
        ])

    # Convert to bytes for download
    output.seek(0)
    byte_output = BytesIO()
    byte_output.write(output.getvalue().encode('utf-8'))
    byte_output.seek(0)

    # Generate filename with timestamp
    filename = f'dpc_practices_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'

    return send_file(
        byte_output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/export/json', methods=['GET'])
def export_json():
    """Export practices to JSON"""

    # Get filter parameters
    status = request.args.get('status')
    search = request.args.get('search')
    include_data = request.args.get('include_data', 'true').lower() == 'true'

    # Build query
    query = Practice.query

    if status:
        query = query.filter_by(enrichment_status=status)

    if search:
        query = query.filter(
            db.or_(
                Practice.practice_name.ilike(f'%{search}%'),
                Practice.practice_id.ilike(f'%{search}%')
            )
        )

    practices = query.all()

    # Build export data
    export_data = []
    for p in practices:
        practice_dict = {
            'practice_id': p.practice_id,
            'practice_name': p.practice_name,
            'website_url': p.website_url,
            'address': {
                'street': p.address_street,
                'city': p.address_city,
                'state': p.address_state,
                'zip': p.address_zip
            },
            'phone': p.phone,
            'enrichment_status': p.enrichment_status,
            'enriched_at': p.enriched_at.isoformat() if p.enriched_at else None
        }

        if include_data and p.data:
            practice_dict['enriched_data'] = p.data

        export_data.append(practice_dict)

    # Create JSON file in memory
    json_str = json.dumps(export_data, indent=2)
    byte_output = BytesIO(json_str.encode('utf-8'))
    byte_output.seek(0)

    # Generate filename with timestamp
    filename = f'dpc_practices_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'

    return send_file(
        byte_output,
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/admin/test-openrouter', methods=['POST'])
def test_openrouter():
    """Test OpenRouter API connection and response (admin only)"""
    from datetime import datetime

    # Simple password protection
    data = request.get_json() or {}
    password = data.get('password', '')

    from app import APP_PASSWORD
    if password != APP_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        import os
        import httpx

        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'OPENROUTER_API_KEY not configured'
            }), 500

        # Test with a simple prompt
        response = httpx.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://dpc-enrichment.app',
                'X-Title': 'DPC Enrichment System'
            },
            json={
                'model': 'google/gemini-2.0-flash-exp:free',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'Respond with just "OK" if you can read this.'
                    }
                ],
                'max_tokens': 10
            },
            timeout=30.0
        )

        response.raise_for_status()
        result = response.json()

        return jsonify({
            'success': True,
            'message': 'OpenRouter API is working',
            'model_used': result.get('model'),
            'response': result.get('choices', [{}])[0].get('message', {}).get('content'),
            'test_timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'OpenRouter API test failed: {str(e)}',
            'test_timestamp': datetime.utcnow().isoformat()
        }), 500


@bp.route('/admin/test-scraperapi', methods=['POST'])
def test_scraperapi():
    """Test ScraperAPI connection (admin only)"""
    from datetime import datetime

    # Simple password protection
    data = request.get_json() or {}
    password = data.get('password', '')

    from app import APP_PASSWORD
    if password != APP_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        import os
        import httpx

        api_key = os.getenv('SCRAPERAPI_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'SCRAPERAPI_KEY not configured'
            }), 500

        # Test with example.com
        test_url = 'https://example.com'
        response = httpx.get(
            'https://api.scraperapi.com',
            params={
                'api_key': api_key,
                'url': test_url
            },
            timeout=30.0
        )

        response.raise_for_status()
        content = response.text

        return jsonify({
            'success': True,
            'message': 'ScraperAPI is working',
            'test_url': test_url,
            'response_length': len(content),
            'contains_expected': 'Example Domain' in content,
            'test_timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'ScraperAPI test failed: {str(e)}',
            'test_timestamp': datetime.utcnow().isoformat()
        }), 500


@bp.route('/admin/reverse-geocode', methods=['POST'])
def reverse_geocode_addresses():
    """Reverse geocode practices with lat/long but missing addresses (admin only)"""
    from datetime import datetime
    import time

    # Simple password protection
    data = request.get_json() or {}
    password = data.get('password', '')

    from app import APP_PASSWORD
    if password != APP_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError

        # Initialize geocoder with a custom user agent
        geolocator = Nominatim(user_agent="dpc-enrichment-app")

        # Find practices with lat/long but missing address
        practices_to_geocode = Practice.query.filter(
            Practice.latitude.isnot(None),
            Practice.longitude.isnot(None),
            db.or_(
                Practice.address_street.is_(None),
                Practice.address_city.is_(None)
            )
        ).limit(data.get('limit', 100)).all()

        stats = {
            'total_found': len(practices_to_geocode),
            'geocoded': 0,
            'failed': 0,
            'errors': []
        }

        for practice in practices_to_geocode:
            try:
                # Reverse geocode
                location = geolocator.reverse(
                    f"{practice.latitude}, {practice.longitude}",
                    timeout=10,
                    language='en'
                )

                if location and location.raw.get('address'):
                    addr = location.raw['address']

                    # Update practice with address components
                    if not practice.address_street:
                        # Build street address from components
                        street_parts = []
                        if addr.get('house_number'):
                            street_parts.append(addr['house_number'])
                        if addr.get('road'):
                            street_parts.append(addr['road'])
                        elif addr.get('street'):
                            street_parts.append(addr['street'])

                        if street_parts:
                            practice.address_street = ' '.join(street_parts)

                    if not practice.address_city:
                        practice.address_city = (
                            addr.get('city') or
                            addr.get('town') or
                            addr.get('village') or
                            addr.get('hamlet') or
                            addr.get('county')
                        )

                    if not practice.address_state:
                        # Use state abbreviation to fit VARCHAR(10) constraint
                        state_full = addr.get('state')
                        if state_full:
                            # Map full state names to abbreviations
                            state_map = {
                                'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
                                'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
                                'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
                                'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
                                'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
                                'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
                                'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
                                'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
                                'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
                                'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
                                'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
                                'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
                                'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC'
                            }
                            practice.address_state = state_map.get(state_full, state_full[:10])

                    if not practice.address_zip:
                        practice.address_zip = addr.get('postcode')

                    practice.updated_at = datetime.utcnow()

                    stats['geocoded'] += 1

                    # Commit every 10 practices
                    if stats['geocoded'] % 10 == 0:
                        db.session.commit()

                    # Rate limiting - Nominatim has 1 request per second limit
                    time.sleep(1.1)

                else:
                    stats['failed'] += 1
                    stats['errors'].append(f"{practice.practice_id}: No address found")

            except (GeocoderTimedOut, GeocoderServiceError) as e:
                stats['failed'] += 1
                stats['errors'].append(f"{practice.practice_id}: {str(e)}")
                time.sleep(2)  # Extra delay on error
                continue
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"{practice.practice_id}: {str(e)}")
                continue

        # Final commit
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'error': f'Failed to commit: {str(e)}',
                'stats': stats
            }), 500

        return jsonify({
            'success': True,
            'message': f'Reverse geocoded {stats["geocoded"]} practices',
            'stats': stats
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to reverse geocode: {str(e)}'}), 500


@bp.route('/admin/load-practices', methods=['POST'])
def load_practices():
    """Load practices from JSON file into database (admin only)"""
    import os
    import json
    from datetime import datetime

    # Simple password protection
    data = request.get_json() or {}
    password = data.get('password', '')

    from app import APP_PASSWORD
    if password != APP_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    # Path to JSON file
    json_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'dpc_complete_2763_practices_with_corrected_urls.json'
    )

    if not os.path.exists(json_file):
        return jsonify({'error': f'JSON file not found: {json_file}'}), 404

    try:
        # Load JSON data
        with open(json_file, 'r', encoding='utf-8') as f:
            file_data = json.load(f)

        practices_data = file_data.get('practices', [])
        metadata = file_data.get('metadata', {})

        # Check existing practices
        existing_ids = {p.practice_id for p in db.session.query(Practice.practice_id).all()}

        # Statistics
        stats = {
            'total': len(practices_data),
            'added': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': []
        }

        # Load practices
        for practice_data in practices_data:
            practice_id = practice_data.get('practice_id')

            if not practice_id:
                stats['errors'] += 1
                stats['error_details'].append(f"Missing practice_id: {practice_data.get('practice_name')}")
                continue

            # Skip if already exists
            if practice_id in existing_ids:
                stats['skipped'] += 1
                continue

            try:
                # Create Practice instance
                practice = Practice(
                    practice_id=practice_id,
                    practice_name=practice_data.get('practice_name'),
                    website_url=practice_data.get('website_url'),
                    address_street=practice_data.get('address_street'),
                    address_city=practice_data.get('address_city'),
                    address_state=practice_data.get('address_state'),
                    address_zip=practice_data.get('address_zip'),
                    phone=practice_data.get('phone'),
                    latitude=practice_data.get('latitude'),
                    longitude=practice_data.get('longitude'),
                    enrichment_status='pending',
                    data=practice_data,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )

                db.session.add(practice)
                stats['added'] += 1

                # Commit every 100 practices to avoid memory issues
                if stats['added'] % 100 == 0:
                    db.session.commit()

            except Exception as e:
                stats['errors'] += 1
                stats['error_details'].append(f"{practice_id}: {str(e)}")
                db.session.rollback()
                continue

        # Final commit
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'error': f'Failed to commit: {str(e)}',
                'stats': stats
            }), 500

        # Return statistics
        return jsonify({
            'success': True,
            'message': 'Practices loaded successfully',
            'metadata': metadata,
            'stats': stats,
            'total_in_db': Practice.query.count()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to load practices: {str(e)}'}), 500


@bp.route('/admin/check-run/<int:run_id>', methods=['GET'])
def check_run(run_id):
    """Check enrichment run details (admin only)"""
    try:
        from app import APP_PASSWORD

        password = request.args.get('password', '')
        if password != APP_PASSWORD:
            return jsonify({'error': 'Unauthorized'}), 401

        run = EnrichmentRun.query.get(run_id)
        if not run:
            return jsonify({'error': 'Run not found'}), 404

        # Get practices enriched in this run
        practices = Practice.query.filter_by(run_id=run_id).all()

        practice_details = []
        for p in practices:
            details = {
                'id': p.id,
                'practice_id': p.practice_id,
                'practice_name': p.practice_name,
                'enrichment_status': p.enrichment_status,
                'enriched_at': p.enriched_at.isoformat() if p.enriched_at else None
            }

            if p.data:
                # Count missing values
                na_fields = [k for k, v in p.data.items() if v == '-NA-']
                neg_one_fields = [k for k, v in p.data.items() if v == -1]
                details['data_fields'] = len(p.data)
                details['na_count'] = len(na_fields)
                details['neg_one_count'] = len(neg_one_fields)
                details['sample_na_fields'] = na_fields[:5]

            practice_details.append(details)

        return jsonify({
            'run': {
                'id': run.id,
                'status': run.status,
                'total_practices': run.total_practices,
                'successful': run.successful,
                'failed': run.failed,
                'skipped': run.skipped,
                'success_rate': run.success_rate,
                'total_cost': float(run.total_cost or 0),
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'config': run.config,
                'statistics': run.statistics
            },
            'practices': practice_details
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': 'Internal server error',
            'details': str(e),
            'traceback': traceback.format_exc()
        }), 500


@bp.route('/admin/list-runs', methods=['GET'])
def list_runs():
    """List all enrichment runs (admin only)"""
    try:
        from app import APP_PASSWORD

        password = request.args.get('password', '')
        if password != APP_PASSWORD:
            return jsonify({'error': 'Unauthorized'}), 401

        runs = EnrichmentRun.query.order_by(EnrichmentRun.id.desc()).limit(10).all()

        return jsonify({
            'runs': [
                {
                    'id': r.id,
                    'status': r.status,
                    'total_practices': r.total_practices,
                    'successful': r.successful,
                    'failed': r.failed,
                    'started_at': r.started_at.isoformat() if r.started_at else None,
                    'completed_at': r.completed_at.isoformat() if r.completed_at else None
                }
                for r in runs
            ]
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': 'Internal server error',
            'details': str(e),
            'traceback': traceback.format_exc()
        }), 500


@bp.route('/version', methods=['GET'])
def get_version():
    """Get deployed version info"""
    import os
    commit_file = os.path.join(os.path.dirname(__file__), '../..', 'git_commit.txt')

    try:
        if os.path.exists(commit_file):
            with open(commit_file, 'r') as f:
                commit = f.read().strip()
        else:
            commit = 'unknown (file not found)'
    except Exception as e:
        commit = f'error: {str(e)}'

    return jsonify({
        'commit': commit,
        'timestamp': datetime.utcnow().isoformat()
    })


@bp.route('/export/enriched', methods=['GET'])
def export_enriched_only():
    """Export only enriched practice data (AI-extracted fields)"""

    # Get only completed practices
    practices = Practice.query.filter_by(enrichment_status='completed').all()

    export_data = []
    for p in practices:
        if p.data:
            # Create enriched practice dict with base info + AI fields
            practice_dict = {
                'practice_id': p.practice_id,
                'practice_name': p.practice_name,
                'website_url': p.website_url,
                **p.data  # Merge enriched fields
            }
            export_data.append(practice_dict)

    # Create JSON file
    json_str = json.dumps(export_data, indent=2)
    byte_output = BytesIO(json_str.encode('utf-8'))
    byte_output.seek(0)

    filename = f'dpc_enriched_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'

    return send_file(
        byte_output,
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )
