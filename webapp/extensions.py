"""
Flask extensions for DPC Enrichment Web App

This module initializes all Flask extensions to avoid circular imports.
"""

from flask_sqlalchemy import SQLAlchemy

# Initialize extensions
db = SQLAlchemy()
