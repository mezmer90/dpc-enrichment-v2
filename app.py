"""
Flask App Factory for DPC Enrichment Web App

Entry point for Railway deployment.
"""

import sys
print("DEBUG: app.py module loading started", file=sys.stderr, flush=True)

import os
from flask import Flask, session, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
from functools import wraps

print("DEBUG: Imports complete", file=sys.stderr, flush=True)

# Initialize extensions
db = SQLAlchemy()
print("DEBUG: SQLAlchemy initialized", file=sys.stderr, flush=True)

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
    print("DEBUG: create_app() called", file=sys.stderr, flush=True)
    # Configure template and static folders to point to webapp directory
    app = Flask(
        __name__,
        template_folder='webapp/templates',
        static_folder='webapp/static'
    )
    print("DEBUG: Flask app instance created", file=sys.stderr, flush=True)

    # Configuration
    if config_name == 'production' or os.getenv('RAILWAY_ENVIRONMENT'):
        print("DEBUG: Loading ProductionConfig", file=sys.stderr, flush=True)
        app.config.from_object('webapp.config.ProductionConfig')
    else:
        print("DEBUG: Loading DevelopmentConfig", file=sys.stderr, flush=True)
        app.config.from_object('webapp.config.DevelopmentConfig')

    print(f"DEBUG: DATABASE_URL = {app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')[:50]}...", file=sys.stderr, flush=True)

    # Initialize extensions
    print("DEBUG: Initializing db with app", file=sys.stderr, flush=True)
    db.init_app(app)
    print("DEBUG: db.init_app() complete", file=sys.stderr, flush=True)

    # Register blueprints
    print("DEBUG: Importing blueprints", file=sys.stderr, flush=True)
    from webapp.routes import main, api
    print("DEBUG: Blueprint imports complete", file=sys.stderr, flush=True)
    app.register_blueprint(main.bp)
    print("DEBUG: main blueprint registered", file=sys.stderr, flush=True)
    app.register_blueprint(api.bp, url_prefix='/api')
    print("DEBUG: api blueprint registered", file=sys.stderr, flush=True)

    # Create database tables (only in development, not on Railway)
    # On Railway, tables are created on first request to avoid blocking startup
    print("DEBUG: Setting up database table creation", file=sys.stderr, flush=True)
    if not os.getenv('RAILWAY_ENVIRONMENT'):
        print("DEBUG: Development mode - creating tables now", file=sys.stderr, flush=True)
        with app.app_context():
            db.create_all()
        print("DEBUG: Tables created", file=sys.stderr, flush=True)
    else:
        print("DEBUG: Railway mode - skipping table creation at startup", file=sys.stderr, flush=True)

    # Create tables on first request (Railway only)
    @app.before_request
    def create_tables_on_first_request():
        if os.getenv('RAILWAY_ENVIRONMENT') and not hasattr(create_tables_on_first_request, 'done'):
            try:
                print("DEBUG: Creating tables on first request", file=sys.stderr, flush=True)
                db.create_all()
                create_tables_on_first_request.done = True
                app.logger.info("Database tables created successfully on first request")
            except Exception as e:
                app.logger.error(f"Failed to create database tables: {e}")

    # Simple password protection middleware
    print("DEBUG: Setting up password protection middleware", file=sys.stderr, flush=True)
    @app.before_request
    def check_password():
        # Allow health check, login, logout, and static files
        if request.path in ['/health', '/login', '/logout'] or request.path.startswith('/static'):
            return None

        # Check if authenticated
        if not session.get('authenticated'):
            return redirect(url_for('main.login'))

    # Health check endpoint for Railway
    print("DEBUG: Setting up health check endpoint", file=sys.stderr, flush=True)
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'dpc-enrichment-web'}, 200

    print("DEBUG: create_app() returning app instance", file=sys.stderr, flush=True)
    return app


# Create app instance for WSGI servers (Gunicorn, etc.)
print("DEBUG: Creating module-level app instance", file=sys.stderr, flush=True)
try:
    app = create_app()
    print("DEBUG: Module-level app instance created successfully!", file=sys.stderr, flush=True)
except Exception as e:
    print(f"FATAL ERROR creating app: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    raise

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
