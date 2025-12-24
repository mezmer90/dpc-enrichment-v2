"""
Main web routes - Dashboard and UI pages
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from webapp.models import EnrichmentRun, Practice, APIStatus
from app import db

bp = Blueprint('main', __name__)


@bp.route('/')
@login_required
def index():
    """Dashboard - main page"""

    # Get current run status
    current_run = EnrichmentRun.query.filter(
        EnrichmentRun.status.in_(['running', 'paused'])
    ).first()

    # Get statistics
    total_practices = Practice.query.count()
    completed = Practice.query.filter_by(enrichment_status='completed').count()
    failed = Practice.query.filter_by(enrichment_status='failed').count()
    pending = Practice.query.filter_by(enrichment_status='pending').count()

    # Get API status
    api_statuses = APIStatus.query.all()

    # Recent runs
    recent_runs = EnrichmentRun.query.order_by(
        EnrichmentRun.created_at.desc()
    ).limit(5).all()

    return render_template(
        'dashboard.html',
        current_run=current_run,
        total_practices=total_practices,
        completed=completed,
        failed=failed,
        pending=pending,
        api_statuses=api_statuses,
        recent_runs=recent_runs
    )


@bp.route('/progress')
@login_required
def progress():
    """Real-time progress monitor"""

    current_run = EnrichmentRun.query.filter(
        EnrichmentRun.status.in_(['running', 'paused'])
    ).first()

    return render_template('progress.html', current_run=current_run)


@bp.route('/practices')
@login_required
def practices():
    """List all practices"""

    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')

    query = Practice.query

    if status_filter != 'all':
        query = query.filter_by(enrichment_status=status_filter)

    practices_paginated = query.order_by(
        Practice.updated_at.desc()
    ).paginate(page=page, per_page=50)

    return render_template(
        'practices.html',
        practices=practices_paginated,
        status_filter=status_filter
    )


@bp.route('/runs')
@login_required
def runs():
    """Enrichment run history"""

    page = request.args.get('page', 1, type=int)

    runs_paginated = EnrichmentRun.query.order_by(
        EnrichmentRun.created_at.desc()
    ).paginate(page=page, per_page=20)

    return render_template('runs.html', runs=runs_paginated)


@bp.route('/settings')
@login_required
def settings():
    """API and system settings"""

    api_statuses = APIStatus.query.all()

    return render_template('settings.html', api_statuses=api_statuses)
