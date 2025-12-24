"""
Flask App Factory for DPC Enrichment Web App

Entry point for Railway deployment.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from pathlib import Path

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()


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
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Register blueprints
    from webapp.routes import main, api, auth
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp, url_prefix='/api')
    app.register_blueprint(auth.bp, url_prefix='/auth')

    # Create database tables
    with app.app_context():
        db.create_all()

    # Health check endpoint for Railway
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'dpc-enrichment-web'}, 200

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
