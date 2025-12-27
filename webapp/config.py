"""
Configuration for Flask App
"""

import os
from pathlib import Path


class Config:
    """Base configuration"""

    # Flask
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Authentication
    APP_PASSWORD = os.getenv('APP_PASSWORD', 'dpc2025')

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'sqlite:///dpc_enrichment.db'
    ).replace('postgres://', 'postgresql://')  # Railway uses postgres://

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Verify connections before using
        'pool_recycle': 300,    # Recycle connections after 5 minutes
    }

    # Redis (for Celery)
    # Handle empty REDIS_URL by falling back to default
    REDIS_URL = os.getenv('REDIS_URL') or 'redis://localhost:6379/0'

    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # API Keys (from environment)
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    SCRAPERAPI_KEY = os.getenv('SCRAPERAPI_KEY')

    # Enrichment settings
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', 6))
    CHECKPOINT_INTERVAL = int(os.getenv('CHECKPOINT_INTERVAL', 1))

    # File storage
    BASE_DIR = Path(__file__).parent.parent
    MARKDOWN_DIR = BASE_DIR / 'data' / 'markdown'
    ENRICHED_DIR = BASE_DIR / 'data' / 'enriched'

    # Session (uses Flask's default secure cookie-based sessions)
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration (Railway)"""
    DEBUG = False
    TESTING = False

    # Force HTTPS on Railway
    PREFERRED_URL_SCHEME = 'https'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
