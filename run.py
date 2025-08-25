#!/usr/bin/env python3
"""
Sports Coaching Management System
Main application entry point
"""

from app.app import create_app

if __name__ == '__main__':
    app, celery = create_app()
    app.run(
        host=app.config.get('APP_HOST', '0.0.0.0'),
        port=app.config.get('APP_PORT', 5000),
        debug=app.config.get('DEBUG', False)
    ) 