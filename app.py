"""
Flask App Factory for DPC Enrichment Web App

Entry point for Railway deployment.
"""

import os
from flask import Flask, session, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
from functools import wraps

# Initialize extensions
db = SQLAlchemy()

# Simple password protection
APP_PASSWORD = os.getenv('APP_PASSWORD', 'dpc2025')  # Change in production!


def require_password(f):
    """Decorator to require password for route access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow health check and static files
        if request.path in ['/health', '/login', '/logout'] or request.path.startswith('/static'):
            return f(*args, **kwargs)

        # Check if authenticated
        if not session.get('authenticated'):
            return redirect(url_for('main.login'))

        return f(*args, **kwargs)
    return decorated_function


def create_app(config_name=None):
    """
    Create and configure Flask application.

    Args:
        config_name: Configuration name (development, production, etc.)

    Returns:
        Configured Flask app
    """
    app = Flask(__name__)

    # Configuration
    if config_name == 'production' or os.getenv('RAILWAY_ENVIRONMENT'):
        app.config.from_object('webapp.config.ProductionConfig')
    else:
        app.config.from_object('webapp.config.DevelopmentConfig')

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    from webapp.routes import main, api
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp, url_prefix='/api')

    # Create database tables
    with app.app_context():
        db.create_all()

    # Simple password protection middleware
    @app.before_request
    def check_password():
        # Allow health check, login, logout, and static files
        if request.path in ['/health', '/login', '/logout'] or request.path.startswith('/static'):
            return None

        # Check if authenticated
        if not session.get('authenticated'):
            return redirect(url_for('main.login'))

    # Health check endpoint for Railway
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'dpc-enrichment-web'}, 200

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
