"""
Database Models for DPC Enrichment Web App
"""

from datetime import datetime
from webapp.extensions import db


class Practice(db.Model):
    """Practice model - stores DPC practice data"""

    __tablename__ = 'practices'

    id = db.Column(db.Integer, primary_key=True)
    practice_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    practice_name = db.Column(db.String(500))
    website_url = db.Column(db.Text)

    # Address
    address_street = db.Column(db.String(500))
    address_city = db.Column(db.String(200))
    address_state = db.Column(db.String(10))
    address_zip = db.Column(db.String(20))

    # Contact
    phone = db.Column(db.String(50))
    latitude = db.Column(db.Numeric(10, 7))
    longitude = db.Column(db.Numeric(10, 7))

    # Enrichment status
    enrichment_status = db.Column(
        db.String(50),
        default='pending',
        index=True
    )  # pending, in_progress, completed, failed, skipped

    enriched_at = db.Column(db.DateTime)

    # Full enriched data as JSON
    data = db.Column(db.JSON)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    run_id = db.Column(db.Integer, db.ForeignKey('enrichment_runs.id'))

    def __repr__(self):
        return f'<Practice {self.practice_id}: {self.practice_name}>'


class EnrichmentRun(db.Model):
    """Enrichment run model - tracks each enrichment session"""

    __tablename__ = 'enrichment_runs'

    id = db.Column(db.Integer, primary_key=True)

    # Status
    status = db.Column(
        db.String(50),
        default='pending',
        index=True
    )  # pending, running, paused, completed, failed

    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    paused_at = db.Column(db.DateTime)

    # Statistics
    total_practices = db.Column(db.Integer, default=0)
    successful = db.Column(db.Integer, default=0)
    failed = db.Column(db.Integer, default=0)
    skipped = db.Column(db.Integer, default=0)

    # Costs and performance
    total_cost = db.Column(db.Numeric(10, 4), default=0)
    total_time = db.Column(db.Integer)  # seconds

    # Configuration
    config = db.Column(db.JSON)  # Run configuration
    statistics = db.Column(db.JSON)  # Detailed statistics

    # User tracking
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    practices = db.relationship('Practice', backref='run', lazy='dynamic')

    @property
    def success_rate(self):
        """Calculate success rate"""
        if self.total_practices == 0:
            return 0
        return (self.successful / self.total_practices) * 100

    @property
    def is_running(self):
        """Check if run is currently active"""
        return self.status == 'running'

    @property
    def is_paused(self):
        """Check if run is paused"""
        return self.status == 'paused'

    @property
    def can_resume(self):
        """Check if run can be resumed"""
        return self.status in ['paused', 'failed']

    def __repr__(self):
        return f'<EnrichmentRun {self.id}: {self.status}>'


class APIStatus(db.Model):
    """API status model - tracks API health and issues"""

    __tablename__ = 'api_status'

    id = db.Column(db.Integer, primary_key=True)

    # API details
    api_name = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(
        db.String(50),
        default='active'
    )  # active, paused, budget_exceeded, rate_limited

    # Error tracking
    last_error = db.Column(db.Text)
    error_count = db.Column(db.Integer, default=0)

    # Pause/resume tracking
    paused_at = db.Column(db.DateTime)
    resumed_at = db.Column(db.DateTime)
    pause_reason = db.Column(db.String(200))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_healthy(self):
        """Check if API is healthy"""
        return self.status == 'active'

    @property
    def is_paused(self):
        """Check if API is paused"""
        return self.status in ['paused', 'budget_exceeded', 'rate_limited']

    def __repr__(self):
        return f'<APIStatus {self.api_name}: {self.status}>'
